import importlib.util
import json
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / 'runtime.py'
spec = importlib.util.spec_from_file_location('runtime_v2', MODULE_PATH)
runtime = importlib.util.module_from_spec(spec); sys.modules[spec.name] = runtime; spec.loader.exec_module(runtime)

class RuntimeV2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.con = runtime.connect(self.root / 'test.sqlite3')
        self.account, self.project, self.chat = 'acct1', 'memory-prism', 'chat-a'
    def tearDown(self):
        self.con.close(); self.tmp.cleanup()
    def ev(self, typ, provenance, content, **kwargs):
        return runtime.append_event(self.con, account=self.account, project=self.project, chat=self.chat,
                                    event_type=typ, provenance=provenance, content=content, **kwargs)
    def test_history_is_append_only_projection_hides_rejected_branch(self):
        self.ev('initial_brief','user','Preserve the actual task.')
        runtime.propose_branch(self.con,account=self.account,project=self.project,chat=self.chat,
          branch_id='b1',label='Wrong frame',tradeoff='fast but changes thesis',strategy_key='wrong-metaphor')
        self.ev('generated_output','assistant','Rejected wrong draft',branch_id='b1',authority='none',inference_kind='generated_artifact')
        out=runtime.decide_branch(self.con,account=self.account,project=self.project,chat=self.chat,
          branch_id='b1',status='rejected',note='Wrong direction',strategy_failure=True)
        payload=runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat)
        self.assertTrue(any(e['content']=='Rejected wrong draft' for e in payload['excluded_from_active_context']))
        self.assertFalse(any(e['content']=='Rejected wrong draft' for e in payload['active_events']))
        self.assertTrue(any(e['content']=='Wrong direction' for e in payload['active_events']))
        rendered=runtime.render_markdown(payload)
        self.assertNotIn('Rejected wrong draft', rendered)
        self.assertNotIn('Wrong frame', rendered)
        self.assertEqual(payload['branch_statuses']['b1'],'rejected')
        self.assertEqual(len(runtime.scope_events(self.con,self.account,self.project,self.chat)),4)
        self.assertFalse(out['circuit_breaker_triggered'])
    def test_branch_ids_are_scoped_to_chat(self):
        runtime.propose_branch(self.con,account=self.account,project=self.project,chat=self.chat,branch_id='same',label='A',tradeoff='tradeoff A',strategy_key='A')
        runtime.propose_branch(self.con,account=self.account,project=self.project,chat='chat-b',branch_id='same',label='A elsewhere',tradeoff='tradeoff B',strategy_key='A')
        rows=self.con.execute('SELECT branch_id,chat_id FROM branches WHERE branch_id=? ORDER BY chat_id',('same',)).fetchall()
        self.assertEqual({r['chat_id'] for r in rows},{'chat-a','chat-b'})
    def test_event_ledger_rejects_update_and_delete(self):
        e=self.ev('observation','user','Original wording')
        with self.assertRaises(Exception):
            self.con.execute('UPDATE events SET content=? WHERE seq=?',('rewritten',e['seq']))
        with self.assertRaises(Exception):
            self.con.execute('DELETE FROM events WHERE seq=?',(e['seq'],))
    def test_user_and_ai_claim_dimensions_are_separate(self):
        e=self.ev('decision','user','Choose option B',authority='user_direct',inference_kind='decision',truth_status='not_applicable',source_ref='turn-5')
        self.assertEqual(e['provenance'],'user')
        self.assertEqual(e['authority'],'user_direct')
        self.assertEqual(e['inference_kind'],'decision')
        self.assertEqual(e['truth_status'],'not_applicable')
        ai=self.ev('analysis','assistant','Likely explanation',authority='none',inference_kind='inference')
        self.assertNotEqual(ai['authority'],e['authority'])
        with self.assertRaises(ValueError):
            self.ev('decision','user','bad authority',authority='verified_truth')
    def test_chat_switch_destroys_and_rehydrates_local_context(self):
        self.ev('initial_brief','user','Only for chat A')
        session=runtime.RuntimeSession(self.con,account=self.account)
        c1=session.open_chat(self.project,self.chat)
        c2=session.open_chat(self.project,'chat-b')
        self.assertNotEqual(c1.runtime_instance_id,c2.runtime_instance_id)
        self.assertIsNone(session.local_context if session.local_context and session.local_context.chat_id=='chat-a' else None)
        self.assertIn('destroyed:memory-prism/chat-a',session.lifecycle_log[1])
        self.assertFalse(any(e['content']=='Only for chat A' for e in c2.payload['active_events']))
    def test_pivot_discards_dirty_context_and_rehydrates(self):
        self.ev('original_query','user','Original request')
        runtime.propose_branch(self.con,account=self.account,project=self.project,chat=self.chat,branch_id='p1',label='A',tradeoff='trade-off A',strategy_key='A')
        self.ev('generated_output','assistant','bad generation',branch_id='p1',authority='none',inference_kind='generated_artifact')
        s=runtime.RuntimeSession(self.con,account=self.account); c=s.open_chat(self.project,self.chat); old=c.runtime_instance_id
        s.pivot_with_reset('p1','User rejected the strategy')
        self.assertNotEqual(old,s.local_context.runtime_instance_id)
        self.assertFalse(any(e['content']=='bad generation' for e in s.local_context.payload['active_events']))
        self.assertTrue(any(e['content']=='User rejected the strategy' for e in s.local_context.payload['active_events']))
    def test_circuit_breaker_counts_same_strategy_rejections_not_edits(self):
        for i in range(2):
            bid=f'b{i}'
            runtime.propose_branch(self.con,account=self.account,project=self.project,chat=self.chat,branch_id=bid,label='Same approach',tradeoff='same cost',strategy_key='same')
            res=runtime.decide_branch(self.con,account=self.account,project=self.project,chat=self.chat,branch_id=bid,status='rejected',note='No',strategy_failure=True,threshold=3)
            self.assertFalse(res['circuit_breaker_triggered'])
            self.ev('correction','user',f'Edit detail {i}')
        runtime.propose_branch(self.con,account=self.account,project=self.project,chat=self.chat,branch_id='b2',label='Same approach',tradeoff='same cost',strategy_key='same')
        res=runtime.decide_branch(self.con,account=self.account,project=self.project,chat=self.chat,branch_id='b2',status='rejected',note='Still wrong',strategy_failure=True,threshold=3)
        self.assertTrue(res['circuit_breaker_triggered'])
    def test_circuit_breaker_run_breaks_after_successful_branch(self):
        for bid in ['fail-1','fail-2']:
            runtime.propose_branch(self.con,account=self.account,project=self.project,chat=self.chat,branch_id=bid,label='Same approach',tradeoff='same cost',strategy_key='same')
            runtime.decide_branch(self.con,account=self.account,project=self.project,chat=self.chat,branch_id=bid,status='rejected',note='wrong',strategy_failure=True,threshold=3)
        runtime.propose_branch(self.con,account=self.account,project=self.project,chat=self.chat,branch_id='success',label='Working path',tradeoff='cost',strategy_key='other')
        runtime.decide_branch(self.con,account=self.account,project=self.project,chat=self.chat,branch_id='success',status='selected')
        runtime.propose_branch(self.con,account=self.account,project=self.project,chat=self.chat,branch_id='fail-3',label='Same approach',tradeoff='same cost',strategy_key='same')
        res=runtime.decide_branch(self.con,account=self.account,project=self.project,chat=self.chat,branch_id='fail-3',status='rejected',note='still wrong',strategy_failure=True,threshold=3)
        self.assertFalse(res['circuit_breaker_triggered'])
        self.assertEqual(res['consecutive_strategy_rejections'],1)
    def test_dormant_memory_is_readable_but_does_not_influence(self):
        e=self.ev('correction','user','Use recurring maintenance, not renewal-from-damage')
        mid=runtime.add_memory(self.con,account=self.account,scope='account',tag='visual-metaphor',claim='Prefer continuous recurring maintenance framing',source_event_seq=e['seq'])
        runtime.review_memory_claim(self.con,mid,'accept')
        runtime.resolve_memory_reference(self.con,mid,'keep')
        p=runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat,relevance_tags={'visual-metaphor'})
        self.assertEqual(len(p['memories_influencing_context']),1)
        runtime.change_memory_state(self.con,mid,'dormant')
        p=runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat,relevance_tags={'visual-metaphor'})
        self.assertEqual(len(p['memories_influencing_context']),0)
        m=runtime.list_memories(self.con,account=self.account)[0]
        self.assertEqual(m['state'],'dormant'); self.assertEqual(m['read_permission'],1); self.assertEqual(m['influence_permission'],0)
        runtime.change_memory_state(self.con,mid,'reverse')
        with self.assertRaises(ValueError):
            runtime.change_memory_state(self.con,mid,'confirm')
        m=runtime.list_memories(self.con,account=self.account)[0]
        self.assertEqual(m['state'],'reversed'); self.assertEqual(m['read_permission'],1); self.assertEqual(m['influence_permission'],0)
        history=self.con.execute('SELECT event_type,to_state FROM memory_events WHERE memory_id=? ORDER BY seq',(mid,)).fetchall()
        self.assertEqual([h['event_type'] for h in history],['memory.proposed_local','memory.accepted_and_pushed','memory.marked_useful','memory.dormant','memory.reverse'])
    def test_old_assistant_turns_stop_influencing_but_remain_verbatim_in_history(self):
        for i in range(5):
            self.ev('assistant_turn','assistant',f'Assistant output {i}')
        self.ev('initial_brief','user','Keep this user brief verbatim')
        payload=runtime.context_projection(self.con,account=self.account,project=self.project,chat=self.chat,recent_assistant_turns=2)
        active=[e['content'] for e in payload['active_events']]
        excluded=[e['content'] for e in payload['excluded_from_active_context']]
        self.assertIn('Assistant output 4',active)
        self.assertIn('Assistant output 3',active)
        self.assertNotIn('Assistant output 0',active)
        self.assertIn('Assistant output 0',excluded)
        self.assertIn('Keep this user brief verbatim',active)
        self.assertEqual(payload['history_event_count'],6)
    def test_gate_has_visible_three_way_choices_and_overrides(self):
        self.assertIn('single-path',runtime.gate_message('single')['message'])
        self.assertTrue(runtime.gate_message('branch')['requires_user_authorization'])
        self.assertIn('recommend',runtime.gate_message('recommend')['message'])
        self.assertIn('reasonable default',runtime.gate_message('just_pick')['message'])
    def test_low_materiality_clarification_is_not_a_formal_branch(self):
        result = runtime.gate_message('clarify')
        self.assertFalse(result['formal_branch_exposure'])
        self.assertFalse(result['requires_user_authorization'])
        self.assertIn('one concise clarifying question', result['message'])
        # The Lancet example is a lexical ambiguity, not a consequential strategy fork.
        self.assertIn('materially determines', runtime.gate_message('branch')['message'])

    def test_rejected_branch_keeps_data_and_records_usage_status(self):
        self.ev('initial_brief','user','Clarify low-cost ambiguity; branch only on material choices.')
        runtime.propose_branch(self.con,account=self.account,project=self.project,chat=self.chat,
          branch_id='instrument',label='Treat Lancet as surgical instrument',tradeoff='Wrong reading if context is the journal cover',strategy_key='lancet-instrument')
        rejected = self.ev('generated_output','assistant','Alternative interpretation retained in history',branch_id='instrument',inference_kind='generated_artifact')
        runtime.decide_branch(self.con,account=self.account,project=self.project,chat=self.chat,
          branch_id='instrument',status='rejected',note='The supplied image is a journal cover; not pertinent now',usage_status='not_pertinent_now')
        payload=runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat)
        self.assertEqual(payload['branch_usage_statuses']['instrument'],'not_pertinent_now')
        self.assertIn(rejected['content'],[e['content'] for e in runtime.scope_events(self.con,self.account,self.project,self.chat)])
        self.assertNotIn(rejected['content'],runtime.render_model_context(payload,max_tokens=10000,token_counter=len)['context_text'])
        self.assertIn('not_pertinent_now',runtime.render_markdown(payload))

    def test_never_try_again_rejection_policy_is_visible_without_reintroducing_branch_artifact(self):
        self.ev('initial_brief','user','Preserve the original goal.')
        runtime.propose_branch(self.con,account=self.account,project=self.project,chat=self.chat,
          branch_id='bad-strategy',label='Bad route',tradeoff='changes the core objective',strategy_key='wrong-route')
        bad=self.ev('generated_output','assistant','Long rejected output must remain historical only.',branch_id='bad-strategy',inference_kind='generated_artifact')
        runtime.decide_branch(self.con,account=self.account,project=self.project,chat=self.chat,
          branch_id='bad-strategy',status='rejected',note='Do not repeat this strategy in this project',usage_status='never_try_again')
        payload=runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat)
        packed=runtime.render_model_context(payload,max_tokens=10000,token_counter=len)
        self.assertIn('usage_policy=never_try_again',packed['context_text'])
        self.assertNotIn(bad['content'],packed['context_text'])
        self.assertEqual(payload['branch_usage_statuses']['bad-strategy'],'never_try_again')

    def test_usage_disposition_retains_data_without_automatic_influence(self):
        source=self.ev('user_correction','user','This alternate framing may be useful in a different context.')
        mid=runtime.add_memory(self.con,account=self.account,scope='account',tag='lancet-instrument',claim='Alternative reading: lancet as a surgical instrument',source_event_seq=source['seq'])
        runtime.review_memory_claim(self.con,mid,'accept')
        result=runtime.resolve_memory_reference(self.con,mid,'not_pertinent_now',note='Current material is the journal cover')
        self.assertEqual(result['usage_status'],'not_pertinent_now')
        self.assertTrue(result['data_retained'])
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM memories WHERE memory_id=?',(mid,)).fetchone()[0],1)
        payload=runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat)
        self.assertEqual(payload['memories_influencing_context'],[])
        self.assertNotIn('Alternative reading:',runtime.render_model_context(payload,max_tokens=10000,token_counter=len)['context_text'])
        row=runtime.list_memories(self.con,account=self.account)[0]
        self.assertEqual(row['usage_status'],'not_pertinent_now')
        history=self.con.execute('SELECT to_usage_status FROM memory_events WHERE memory_id=? ORDER BY seq',(mid,)).fetchall()
        self.assertTrue(all(h['to_usage_status'] is not None for h in history))

    def test_use_when_relevant_requires_explicit_applicability_or_always_tag(self):
        source=self.ev('user_correction','user','This preference is only relevant to its matching workflow.')
        mid=runtime.add_memory(self.con,account=self.account,scope='account',tag='writing',claim='Prefer the established essay workflow',source_event_seq=source['seq'])
        runtime.review_memory_claim(self.con,mid,'accept')
        runtime.resolve_memory_reference(self.con,mid,'use')
        no_tags=runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat)
        self.assertEqual(no_tags['memories_influencing_context'],[])
        matching=runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat,relevance_tags={'writing'})
        self.assertEqual([m['memory_id'] for m in matching['memories_influencing_context']],[mid])

    def test_never_try_again_policy_only_injects_for_matching_tag(self):
        source=self.ev('user_correction','user','Do not repeat this failed image strategy.')
        mid=runtime.add_memory(self.con,account=self.account,scope='account',tag='wrong-metaphor',claim='Avoid the one-event renewal-from-damage strategy',source_event_seq=source['seq'])
        runtime.review_memory_claim(self.con,mid,'accept')
        runtime.resolve_memory_reference(self.con,mid,'avoid')
        unrelated=runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat,relevance_tags={'literature'})
        self.assertEqual(unrelated['memories_influencing_context'],[])
        related=runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat,relevance_tags={'wrong-metaphor'})
        self.assertEqual(len(related['memories_influencing_context']),1)
        packed=runtime.render_model_context(related,max_tokens=10000,token_counter=len)
        self.assertIn('AVOID STRATEGY',packed['context_text'])
        self.assertIn('Avoid the one-event renewal-from-damage strategy',packed['context_text'])

    def test_later_and_not_pertinent_are_not_discard_actions(self):
        source=self.ev('observation','user','Temporary possibility; it may matter later.')
        later=runtime.add_memory(self.con,account=self.account,scope='account',tag='maybe-later',claim='Retain for possible future use',source_event_seq=source['seq'])
        runtime.review_memory_claim(self.con,later,'accept')
        result=runtime.resolve_memory_reference(self.con,later,'later')
        self.assertEqual(result['stage'],'shared_reference')
        self.assertEqual(result['usage_status'],'maybe_later')
        self.assertTrue(result['data_retained'])
        allrows=runtime.list_memories(self.con,account=self.account)
        self.assertTrue(any(x['memory_id']==later for x in allrows))
        # A legacy 'discard' caller is safely mapped to a use disposition, not a deletion.
        source2=self.ev('observation','user','A second alternative remains in the record.')
        other=runtime.add_memory(self.con,account=self.account,scope='account',tag='alt',claim='Keep alternate data',source_event_seq=source2['seq'])
        runtime.review_memory_claim(self.con,other,'accept')
        result2=runtime.resolve_memory_reference(self.con,other,'discard')
        self.assertEqual(result2['usage_status'],'not_pertinent_now')
        self.assertNotEqual(result2['stage'],'discarded')
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM memories WHERE memory_id=?',(other,)).fetchone()[0],1)

    def test_checkpoint_round_trip_and_delta_preview(self):
        self.ev('initial_brief','user','Checkpoint me')
        md,js=runtime.checkpoint(self.con,account=self.account,project=self.project,chat=self.chat,out_dir=self.root/'out')
        p=json.loads(js.read_text(encoding='utf-8'))
        self.assertEqual(p['schema_version'],2); self.assertTrue(md.exists())
        d=runtime.delta_preview('alpha\nbeta','alpha\ngamma')
        self.assertEqual(d['added_lines'],1); self.assertEqual(d['removed_lines'],1)
    def test_bounded_model_context_preserves_user_events_verbatim(self):
        brief = self.ev('initial_brief','user','Keep the question exactly as asked: why does the system forget?')
        constraint = self.ev('constraint','user','Do not summarize this constraint; retain exact wording.')
        ai = self.ev('assistant_turn','assistant','A recent assistant answer that may be included.')
        payload = runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat)
        packed = runtime.render_model_context(payload,max_tokens=10000,token_counter=len)
        self.assertIn(brief['content'],packed['context_text'])
        self.assertIn(constraint['content'],packed['context_text'])
        self.assertIn('provenance=user',packed['context_text'])
        self.assertEqual(packed['protected_event_seqs'],[brief['seq'],constraint['seq']])
        self.assertTrue(packed['budget']['fits_estimated_budget'])
        self.assertEqual(packed['budget']['counter'],'injected_provider_counter')

    def test_protected_context_overflow_fails_closed(self):
        e = self.ev('constraint','user','DO NOT DROP: ' + ('essential constraint ' * 100))
        payload = runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat)
        with self.assertRaises(runtime.ProtectedContextOverflow) as ctx:
            runtime.render_model_context(payload,max_tokens=250,token_counter=len)
        self.assertIn(e['seq'],ctx.exception.protected_event_seqs)
        self.assertGreater(ctx.exception.required,ctx.exception.budget)

    def test_optional_event_is_omitted_whole_when_budget_is_tight(self):
        brief = self.ev('initial_brief','user','Preserve the core question.')
        huge = self.ev('assistant_turn','assistant','Generated material that is not allowed to crowd out the brief. ' * 100)
        payload = runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat)
        packed = runtime.render_model_context(payload,max_tokens=850,token_counter=len)
        self.assertIn(brief['content'],packed['context_text'])
        self.assertNotIn('Generated material that is not allowed',packed['context_text'])
        self.assertIn(huge['seq'],[item['seq'] for item in packed['omitted_events']])
        self.assertTrue(all('content' not in item for item in packed['omitted_events']))
        self.assertTrue(packed['budget']['fits_estimated_budget'])

    def test_model_context_builder_never_reintroduces_rejected_branch(self):
        self.ev('initial_brief','user','Keep the thesis about recurring maintenance.')
        runtime.propose_branch(self.con,account=self.account,project=self.project,chat=self.chat,
          branch_id='bad',label='Renewal from damage',tradeoff='one-time recovery framing',strategy_key='wrong-frame')
        bad = self.ev('generated_output','assistant','The rejected draft says renewal from damage.',branch_id='bad',inference_kind='generated_artifact')
        runtime.decide_branch(self.con,account=self.account,project=self.project,chat=self.chat,
          branch_id='bad',status='rejected',note='This must preserve continuous recurring maintenance instead.',strategy_failure=True)
        payload = runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat)
        packed = runtime.render_model_context(payload,max_tokens=10000,token_counter=len)
        self.assertNotIn(bad['content'],packed['context_text'])
        self.assertNotIn('Renewal from damage',packed['context_text'])
        self.assertNotIn('one-time recovery framing',packed['context_text'])
        self.assertIn('continuous recurring maintenance',packed['context_text'])

    def test_only_influencing_memory_is_injected_not_read_only_reference(self):
        e = self.ev('user_correction','user','Use sustained recurrence as the concept.')
        pending = runtime.add_memory(self.con,account=self.account,scope='account',tag='pending',claim='Pending memory should not be injected',source_event_seq=e['seq'])
        runtime.review_memory_claim(self.con,pending,'accept')
        active = runtime.add_memory(self.con,account=self.account,scope='account',tag='active',claim='Ratified recurring-maintenance preference',source_event_seq=e['seq'])
        runtime.review_memory_claim(self.con,active,'accept')
        runtime.resolve_memory_reference(self.con,active,'keep')
        payload = runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat,relevance_tags={'active','pending'})
        packed = runtime.render_model_context(payload,max_tokens=10000,token_counter=len)
        self.assertIn('Ratified recurring-maintenance preference',packed['context_text'])
        self.assertNotIn('Pending memory should not be injected',packed['context_text'])
        self.assertIn(pending,packed['read_only_memory_ids_not_injected'])
        self.assertIn(active,packed['influencing_memory_ids'])

    def test_history_and_context_recover_after_database_reopen(self):
        original = self.ev('initial_brief','user','Original brief survives process restart.')
        self.ev('assistant_turn','assistant','An older response should remain historical only.')
        # Reopen the same database to simulate a fresh runtime process.
        db_path = self.root / 'test.sqlite3'
        self.con.close()
        self.con = runtime.connect(db_path)
        payload = runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat,recent_assistant_turns=0)
        packed = runtime.render_model_context(payload,max_tokens=10000,token_counter=len)
        self.assertIn(original['content'],packed['context_text'])
        self.assertNotIn('An older response should remain historical only.',packed['context_text'])
        self.assertEqual(payload['history_event_count'],2)
        event_texts=[e['content'] for e in runtime.scope_events(self.con,self.account,self.project,self.chat)]
        self.assertIn('An older response should remain historical only.',event_texts)

    def test_memory_cannot_influence_before_review_and_keep(self):
        src=self.ev('user_correction','user','Candidate memory awaiting review.')
        mid=runtime.add_memory(self.con,account=self.account,scope='project',project=self.project,tag='test',claim='not yet ratified',source_event_seq=src['seq'])
        p=runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat,relevance_tags={'test'})
        self.assertEqual(p['memories_influencing_context'],[])
        self.assertEqual(p['read_only_memory_references'],[])
        self.assertEqual(runtime.list_memories(self.con,account=self.account,project=self.project),[])
        self.assertEqual(runtime.list_memories(self.con,account=self.account,project=self.project,include_local=True)[0]['state'],'local_candidate')
        self.assertEqual(runtime.list_memories(self.con,account=self.account,project=self.project,include_local=True)[0]['usage_status'],'not_pertinent_now')
        self.assertNotIn('not yet ratified',runtime.render_markdown(p))
        runtime.review_memory_claim(self.con,mid,'accept')
        p=runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat)
        self.assertEqual(p['memories_influencing_context'],[])
        self.assertEqual(len(p['read_only_memory_references']),1)
        self.assertEqual(p['read_only_memory_references'][0]['influence_permission'],0)
        runtime.resolve_memory_reference(self.con,mid,'keep',note='Approved in batch review')
        p=runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat,relevance_tags={'test'})
        self.assertEqual(len(p['memories_influencing_context']),1)
        self.assertEqual(p['memories_influencing_context'][0]['stage'],'keepable')

    def test_claim_edit_is_traceable_and_reference_has_no_influence(self):
        e=self.ev('user_correction','user','Avoid one-event renewal metaphor; keep continuous recurrence.')
        mid=runtime.add_memory(self.con,account=self.account,scope='account',tag='metaphor',claim='Renewal from damage',source_event_seq=e['seq'])
        pushed=runtime.review_memory_claim(self.con,mid,'edit',edited_claim='Prefer continuous recurring maintenance, not renewal from damage.',note='Corrected to preserve the essay thesis')
        self.assertEqual(pushed['stage'],'shared_reference')
        self.assertFalse(pushed['influence_permission'])
        p=runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat)
        self.assertEqual(p['memories_influencing_context'],[])
        self.assertEqual(p['read_only_memory_references'][0]['claim'],'Prefer continuous recurring maintenance, not renewal from damage.')
        events=self.con.execute('SELECT * FROM memory_events WHERE memory_id=? ORDER BY seq',(mid,)).fetchall()
        self.assertEqual([x['event_type'] for x in events],['memory.proposed_local','memory.edited_and_pushed'])
        self.assertEqual(events[-1]['from_stage'],'local_candidate')
        self.assertEqual(events[-1]['to_stage'],'shared_reference')
        import json
        details=json.loads(events[-1]['note'])
        self.assertEqual(details['prior_claim'],'Renewal from damage')
        self.assertEqual(details['shared_claim'],'Prefer continuous recurring maintenance, not renewal from damage.')

    def test_rejecting_local_candidate_keeps_audit_but_does_not_share_it(self):
        src=self.ev('user_correction','user','One isolated incident is not a general rule.')
        mid=runtime.add_memory(self.con,account=self.account,scope='account',tag='bad',claim='An unwanted generalized lesson',source_event_seq=src['seq'])
        runtime.review_memory_claim(self.con,mid,'reject',note='One incident does not justify this broad rule')
        self.assertEqual(runtime.list_memories(self.con,account=self.account),[])
        self.assertEqual(len(runtime.list_memories(self.con,account=self.account,include_local=True)),1)
        local = runtime.list_memories(self.con,account=self.account,include_local=True)[0]
        self.assertEqual(local['state'],'rejected')
        self.assertEqual(local['usage_status'],'not_pertinent_now')
        p=runtime.hydrate_payload(self.con,account=self.account,project=self.project,chat=self.chat)
        self.assertEqual(p['read_only_memory_references'],[])
        event=self.con.execute('SELECT * FROM memory_events WHERE memory_id=? ORDER BY seq DESC',(mid,)).fetchone()
        self.assertEqual(event['event_type'],'memory.rejected_local')
        self.assertIn('An unwanted generalized lesson',event['note'])

    def test_rejected_candidate_can_be_reopened_without_losing_use_status_or_source(self):
        src=self.ev('user_correction','user','Potential lesson source.')
        mid=runtime.add_memory(self.con,account=self.account,scope='account',tag='later',claim='Maybe useful later',source_event_seq=src['seq'])
        runtime.set_memory_usage_status(self.con,mid,'maybe_later',note='Keep for future consideration')
        runtime.review_memory_claim(self.con,mid,'reject',note='Not ready to promote')
        before=runtime.list_memories(self.con,account=self.account,include_local=True)[0]
        self.assertEqual(before['usage_status'],'maybe_later')
        reopened=runtime.reopen_memory_candidate(self.con,mid,note='New context may make this useful')
        self.assertTrue(reopened['data_retained'])
        self.assertEqual(reopened['state'],'local_candidate')
        self.assertEqual(reopened['usage_status'],'maybe_later')
        rows=self.con.execute('SELECT event_type FROM memory_events WHERE memory_id=? ORDER BY seq',(mid,)).fetchall()
        self.assertEqual([r['event_type'] for r in rows],['memory.proposed_local','memory.local_usage_status_changed','memory.rejected_local','memory.local_candidate_reopened'])

    def test_cannot_skip_claim_review_and_reference_stage(self):
        src=self.ev('user_correction','user','Candidate rule source.')
        mid=runtime.add_memory(self.con,account=self.account,scope='account',tag='rule',claim='Candidate',source_event_seq=src['seq'])
        with self.assertRaises(ValueError):
            runtime.resolve_memory_reference(self.con,mid,'keep')
        with self.assertRaises(ValueError):
            runtime.change_memory_state(self.con,mid,'ratify')
        self.assertEqual(runtime.list_memories(self.con,account=self.account,include_local=True)[0]['stage'],'local_candidate')


    def test_legacy_v23_database_migrates_memory_stages_safely(self):
        legacy_path = self.root / 'legacy-v23.sqlite3'
        legacy_schema = runtime.SCHEMA.replace(
            "  stage TEXT NOT NULL DEFAULT 'shared_reference' CHECK(stage IN ('local_candidate','shared_reference','keepable','discarded')),\n", "")
        legacy_schema = legacy_schema.replace("  usage_status TEXT NOT NULL DEFAULT 'not_pertinent_now' CHECK(usage_status IN ('use_when_relevant','never_try_again','maybe_later','not_pertinent_now')),\n", "")
        legacy_schema = legacy_schema.replace("  from_usage_status TEXT,\n  to_usage_status TEXT,\n", "")
        legacy_schema = legacy_schema.replace("  from_stage TEXT,\n  to_stage TEXT,\n", "")
        old = sqlite3.connect(legacy_path)
        old.executescript(legacy_schema)
        stamp = runtime.now()
        common = (self.account, 'account', None, 'tag', 'claim', None, 1, 0, 1.0, stamp, stamp, stamp)
        old.execute("INSERT INTO memories(memory_id,account_id,scope,project_id,tag,claim,source_event_seq,state,read_permission,influence_permission,weight,created_at,last_confirmed_at,updated_at) VALUES('pending-old',?,?,?,?,?,?,'pending',?,?,?,?,?,?)", common)
        old.execute("INSERT INTO memories(memory_id,account_id,scope,project_id,tag,claim,source_event_seq,state,read_permission,influence_permission,weight,created_at,last_confirmed_at,updated_at) VALUES('active-old',?,?,?,?,?,?,'active',?,?,?,?,?,?)", common)
        old.execute("INSERT INTO memories(memory_id,account_id,scope,project_id,tag,claim,source_event_seq,state,read_permission,influence_permission,weight,created_at,last_confirmed_at,updated_at) VALUES('dormant-old',?,?,?,?,?,?,'dormant',?,?,?,?,?,?)", common)
        old.commit(); old.close()
        migrated = runtime.connect(legacy_path)
        try:
            rows = {r['memory_id']: dict(r) for r in migrated.execute("SELECT * FROM memories WHERE memory_id LIKE '%-old'")}
            self.assertEqual(rows['pending-old']['stage'], 'shared_reference')
            self.assertEqual(rows['active-old']['stage'], 'keepable')
            self.assertEqual(rows['dormant-old']['stage'], 'keepable')
            cols = {r['name'] for r in migrated.execute('PRAGMA table_info(memory_events)')}
            self.assertIn('from_stage', cols); self.assertIn('to_stage', cols)
            self.assertIn('from_usage_status', cols); self.assertIn('to_usage_status', cols)
            self.assertIn('usage_status', {r['name'] for r in migrated.execute('PRAGMA table_info(memories)')})
        finally:
            migrated.close()


    def test_revision_proposal_requires_explicit_decision_before_expansion(self):
        preview = runtime.propose_revision(
            self.con, account=self.account, project=self.project, chat=self.chat,
            proposal_id='rev-approval', artifact_id='essay.md', base_version='v1',
            original_request='Revise the essay while preserving its thesis.',
            delta_summary='Rewrite the introduction to foreground recurring maintenance.',
            impact_summary='Clarifies the thesis; body sections and references remain unchanged.',
            changed_sections=['Introduction', 'Opening paragraph'], base_sha256='base-sha')
        self.assertEqual(preview['state'], 'proposed')
        self.assertTrue(preview['approval_required_before_expansion'])
        self.assertNotIn('full_artifact', preview)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM revision_outputs').fetchone()[0], 0)
        with self.assertRaises(ValueError):
            runtime.expand_revision(self.con, 'rev-approval', artifact_version='v2', content='# Full artifact')

    def test_revision_acceptance_authorizes_only_the_approved_hash(self):
        preview = runtime.propose_revision(
            self.con, account=self.account, project=self.project, chat=self.chat,
            proposal_id='rev-accept', artifact_id='essay.md', base_version='v1',
            original_request='Revise the essay.', delta_summary='Change the section order.',
            impact_summary='Moves the evidence section earlier; no source text changes.',
            changed_sections=['Section order'])
        accepted = runtime.decide_revision(self.con, 'rev-accept', 'accept', note='Delta looks right',
            account=self.account, project=self.project, chat=self.chat)
        self.assertEqual(accepted['approved_proposal_hash'], preview['proposal_hash'])
        with self.assertRaises(ValueError):
            runtime.propose_revision(
                self.con, account=self.account, project=self.project, chat=self.chat,
                proposal_id='rev-accept', artifact_id='essay.md', base_version='v1',
                original_request='Revise the essay.', delta_summary='Different change.',
                impact_summary='Different impact.', changed_sections=['Other'])
        expanded = runtime.expand_revision(self.con, 'rev-accept', artifact_version='v2',
            content='# Revised essay\n\nThe complete artifact follows the approved delta.',
            account=self.account, project=self.project, chat=self.chat)
        self.assertEqual(expanded['state'], 'expanded')
        self.assertTrue(expanded['approval_hash_matched'])
        saved = runtime.revision_output(self.con, 'rev-accept')
        self.assertEqual(saved['content'], '# Revised essay\n\nThe complete artifact follows the approved delta.')
        self.assertEqual(saved['proposal_hash'], preview['proposal_hash'])
        with self.assertRaises(ValueError):
            runtime.decide_revision(self.con, 'rev-accept', 'accept', account=self.account)

    def test_revision_rejection_resets_and_hides_rejected_delta_from_replan(self):
        self.ev('initial_brief', 'user', 'Preserve the original research question.')
        preview = runtime.propose_revision(
            self.con, account=self.account, project=self.project, chat=self.chat,
            proposal_id='rev-reject', artifact_id='report.md', base_version='v3',
            original_request='Revise the research report without changing its question.',
            delta_summary='Replace the empirical approach with a broad opinion essay.',
            impact_summary='Changes the method and weakens testability.',
            changed_sections=['Method', 'Evidence'])
        result = runtime.decide_revision(self.con, 'rev-reject', 'reject',
            note='Wrong direction; retain an empirical comparison.',
            account=self.account, project=self.project, chat=self.chat)
        self.assertEqual(result['state'], 'rejected_reset')
        self.assertTrue(result['retained_in_history'])
        self.assertFalse(result['rejected_delta_in_active_context'])
        replan = runtime.revision_replan_context(self.con, 'rev-reject',
            account=self.account, project=self.project, chat=self.chat)
        serialized = json.dumps(replan, ensure_ascii=False)
        self.assertIn('Revise the research report without changing its question.', serialized)
        self.assertIn('Wrong direction; retain an empirical comparison.', serialized)
        self.assertNotIn('Replace the empirical approach with a broad opinion essay.', serialized)
        self.assertNotIn('Changes the method and weakens testability.', serialized)
        self.assertNotIn('Method', replan['excluded_from_replan'])
        fresh = runtime.propose_revision(
            self.con, account=self.account, project=self.project, chat=self.chat,
            proposal_id='rev-replanned', artifact_id='report.md', base_version='v3',
            original_request='Ignored placeholder because parent supplies original request.',
            delta_summary='Keep the empirical comparison and clarify sample selection.',
            impact_summary='Improves reproducibility without changing the core question.',
            changed_sections=['Method: sample selection'], parent_revision_id='rev-reject')
        self.assertEqual(fresh['original_request'], 'Revise the research report without changing its question.')
        self.assertEqual(fresh['parent_revision_id'], 'rev-reject')
        self.assertNotEqual(fresh['proposal_hash'], preview['proposal_hash'])

    def test_revision_cannot_replan_from_unrejected_parent(self):
        runtime.propose_revision(
            self.con, account=self.account, project=self.project, chat=self.chat,
            proposal_id='rev-parent-proposed', artifact_id='doc.md', base_version='v1',
            original_request='Update this document.', delta_summary='Fix headings.',
            impact_summary='Headings only.', changed_sections=['Headings'])
        with self.assertRaises(ValueError):
            runtime.propose_revision(
                self.con, account=self.account, project=self.project, chat=self.chat,
                proposal_id='rev-child-invalid', artifact_id='doc.md', base_version='v1',
                original_request='Update this document.', delta_summary='Try another heading scheme.',
                impact_summary='Still headings only.', changed_sections=['Headings'],
                parent_revision_id='rev-parent-proposed')

    def test_revision_base_hash_must_match_before_expansion(self):
        runtime.propose_revision(
            self.con, account=self.account, project=self.project, chat=self.chat,
            proposal_id='rev-base-hash', artifact_id='report.md', base_version='v7',
            original_request='Revise report but preserve the base artifact.',
            delta_summary='Clarify the methodology paragraph.',
            impact_summary='One paragraph changes; conclusions stay unchanged.',
            changed_sections=['Methodology paragraph'], base_sha256='expected-base-hash')
        runtime.decide_revision(self.con, 'rev-base-hash', 'accept', account=self.account,
            project=self.project, chat=self.chat)
        with self.assertRaisesRegex(ValueError, 'current_base_sha256 is required'):
            runtime.expand_revision(self.con, 'rev-base-hash', artifact_version='v8', content='expanded artifact',
                account=self.account, project=self.project, chat=self.chat)
        with self.assertRaisesRegex(ValueError, 'Base artifact changed'):
            runtime.expand_revision(self.con, 'rev-base-hash', artifact_version='v8', content='expanded artifact',
                account=self.account, project=self.project, chat=self.chat, current_base_sha256='stale-base-hash')
        # The accepted proposal remains unexpanded; a matching base permits this approved delta to proceed.
        result = runtime.expand_revision(self.con, 'rev-base-hash', artifact_version='v8', content='expanded artifact',
            account=self.account, project=self.project, chat=self.chat, current_base_sha256='expected-base-hash')
        self.assertTrue(result['base_hash_checked'])
        self.assertEqual(result['state'], 'expanded')

    def test_revision_proposals_and_outputs_are_immutable_history(self):
        runtime.propose_revision(
            self.con, account=self.account, project=self.project, chat=self.chat,
            proposal_id='rev-immutable', artifact_id='doc.md', base_version='v1',
            original_request='Update this document.', delta_summary='Move the summary to the top.',
            impact_summary='Changes order only.', changed_sections=['Summary'])
        with self.assertRaises(Exception):
            self.con.execute("UPDATE revision_proposals SET delta_summary='mutated' WHERE proposal_id='rev-immutable'")
        with self.assertRaises(Exception):
            self.con.execute("DELETE FROM revision_proposals WHERE proposal_id='rev-immutable'")
        runtime.decide_revision(self.con, 'rev-immutable', 'accept', account=self.account,
            project=self.project, chat=self.chat)
        runtime.expand_revision(self.con, 'rev-immutable', artifact_version='v2', content='complete output',
            account=self.account, project=self.project, chat=self.chat)
        with self.assertRaises(Exception):
            self.con.execute("UPDATE revision_outputs SET content='mutated' WHERE proposal_id='rev-immutable'")
        with self.assertRaises(Exception):
            self.con.execute("DELETE FROM revision_outputs WHERE proposal_id='rev-immutable'")

    def test_revision_preview_is_scope_checked(self):
        runtime.propose_revision(
            self.con, account=self.account, project=self.project, chat=self.chat,
            proposal_id='rev-scope', artifact_id='doc.md', base_version='v1',
            original_request='Update this document.', delta_summary='Rename one heading.',
            impact_summary='No body change.', changed_sections=['Heading'])
        with self.assertRaises(ValueError):
            runtime.revision_preview(self.con, 'rev-scope', account=self.account,
                project=self.project, chat='different-chat')

    def test_revision_accept_then_reject_prevents_expansion(self):
        runtime.propose_revision(
            self.con, account=self.account, project=self.project, chat=self.chat,
            proposal_id='rev-reconsidered', artifact_id='doc.md', base_version='v1',
            original_request='Update this document.', delta_summary='Replace a broad claim with a bounded claim.',
            impact_summary='Reduces claim strength, preserves supporting evidence.', changed_sections=['Conclusion'])
        runtime.decide_revision(self.con, 'rev-reconsidered', 'accept', account=self.account,
            project=self.project, chat=self.chat)
        rejected = runtime.decide_revision(self.con, 'rev-reconsidered', 'reject', note='Second thought: wrong direction',
            account=self.account, project=self.project, chat=self.chat)
        self.assertEqual(rejected['state'], 'rejected_reset')
        with self.assertRaises(ValueError):
            runtime.expand_revision(self.con, 'rev-reconsidered', artifact_version='v2', content='full output',
                account=self.account, project=self.project, chat=self.chat)


    def test_delta_conformance_passes_for_declared_sections_and_pins_release_readiness(self):
        import hashlib
        base = '# Report\nIntro v1.\n\n## Method\nMethod v1.\n\n## Results\nResults unchanged.\n'
        candidate = '# Report\nIntro v2.\n\n## Method\nMethod v2.\n\n## Results\nResults unchanged.\n'
        base_sha = hashlib.sha256(base.encode('utf-8')).hexdigest()
        runtime.propose_revision(self.con, account=self.account, project=self.project, chat=self.chat,
            proposal_id='rev-conformance-pass', artifact_id='report.md', base_version='v1',
            original_request='Clarify the report introduction and methodology.',
            delta_summary='Update the introduction and methodology only.',
            impact_summary='Results and references remain untouched.',
            changed_sections=['heading:Report', 'heading:Report / Method'], base_sha256=base_sha)
        runtime.decide_revision(self.con, 'rev-conformance-pass', 'accept', account=self.account,
            project=self.project, chat=self.chat)
        runtime.expand_revision(self.con, 'rev-conformance-pass', artifact_version='v2', content=candidate,
            account=self.account, project=self.project, chat=self.chat, current_base_sha256=base_sha)
        report = runtime.verify_revision_output(self.con, 'rev-conformance-pass', base_content=base,
            account=self.account, project=self.project, chat=self.chat)
        self.assertEqual(report['status'], 'pass')
        self.assertTrue(report['ready_for_release'])
        self.assertEqual(report['undeclared_changes'], [])
        output = runtime.revision_output(self.con, 'rev-conformance-pass')
        self.assertTrue(output['ready_for_release'])
        self.assertEqual(output['conformance_status'], 'pass')

    def test_delta_conformance_fails_on_undeclared_section_change_and_requires_replan(self):
        import hashlib
        base = '# Report\nIntro v1.\n\n## Method\nMethod v1.\n\n## Results\nResults v1.\n'
        candidate = '# Report\nIntro v2.\n\n## Method\nMethod v2.\n\n## Results\nResults was silently changed.\n'
        base_sha = hashlib.sha256(base.encode('utf-8')).hexdigest()
        runtime.propose_revision(self.con, account=self.account, project=self.project, chat=self.chat,
            proposal_id='rev-conformance-fail', artifact_id='report.md', base_version='v1',
            original_request='Edit introduction and method only.',
            delta_summary='Update introduction and method.',
            impact_summary='Results must stay unchanged.',
            changed_sections=['heading:Report', 'heading:Report / Method'], base_sha256=base_sha)
        runtime.decide_revision(self.con, 'rev-conformance-fail', 'accept', account=self.account,
            project=self.project, chat=self.chat)
        runtime.expand_revision(self.con, 'rev-conformance-fail', artifact_version='v2', content=candidate,
            account=self.account, project=self.project, chat=self.chat, current_base_sha256=base_sha)
        report = runtime.verify_revision_output(self.con, 'rev-conformance-fail', base_content=base,
            account=self.account, project=self.project, chat=self.chat)
        self.assertEqual(report['status'], 'fail')
        self.assertFalse(report['ready_for_release'])
        self.assertIn('heading:Report / Results', report['undeclared_changes'])
        self.assertEqual(runtime._revision_state(self.con, 'rev-conformance-fail'), 'rejected_reset')
        output = runtime.revision_output(self.con, 'rev-conformance-fail')
        self.assertFalse(output['ready_for_release'])
        replan = runtime.revision_replan_context(self.con, 'rev-conformance-fail',
            account=self.account, project=self.project, chat=self.chat)
        serialized = json.dumps(replan, ensure_ascii=False)
        self.assertIn('Results', replan['user_correction_signal'])
        self.assertNotIn('Results was silently changed', serialized)
        self.assertIn('revision.conformance_failed', [e['event_type'] for e in runtime.revision_history(self.con, 'rev-conformance-fail')])

    def test_delta_conformance_fails_closed_on_vague_or_ambiguous_section_locator(self):
        base = '# Report\nOld intro.\n\n## Method\nOld method.\n'
        candidate = '# Report\nNew intro.\n\n## Method\nOld method.\n'
        report = runtime.check_artifact_conformance(base, candidate, ['intro paragraph'])
        self.assertEqual(report['status'], 'unverifiable')
        self.assertFalse(report['passed'])
        duplicate_base = '# Report\nFirst.\n\n## Notes\nA.\n\n## Notes\nB.\n'
        duplicate_candidate = '# Report\nFirst.\n\n## Notes\nChanged.\n\n## Notes\nB.\n'
        duplicate = runtime.check_artifact_conformance(duplicate_base, duplicate_candidate, ['heading:Report / Notes'])
        self.assertEqual(duplicate['status'], 'unverifiable')

    def test_conformance_refuses_stale_base_and_keeps_candidate_out_of_release(self):
        import hashlib
        base = '# Report\nOriginal.\n'
        candidate = '# Report\nRevised.\n'
        base_sha = hashlib.sha256(base.encode('utf-8')).hexdigest()
        runtime.propose_revision(self.con, account=self.account, project=self.project, chat=self.chat,
            proposal_id='rev-stale-base', artifact_id='report.md', base_version='v1',
            original_request='Change the report.', delta_summary='Rewrite the report.',
            impact_summary='Whole file changes.', changed_sections=['whole-artifact'], base_sha256=base_sha)
        runtime.decide_revision(self.con, 'rev-stale-base', 'accept', account=self.account, project=self.project, chat=self.chat)
        runtime.expand_revision(self.con, 'rev-stale-base', artifact_version='v2', content=candidate,
            account=self.account, project=self.project, chat=self.chat, current_base_sha256=base_sha)
        report = runtime.verify_revision_output(self.con, 'rev-stale-base', base_content='# Report\nExternally modified base.\n',
            account=self.account, project=self.project, chat=self.chat)
        self.assertEqual(report['status'], 'fail')
        self.assertFalse(report['ready_for_release'])
        self.assertEqual(runtime._revision_state(self.con, 'rev-stale-base'), 'rejected_reset')

    def test_whole_artifact_selector_explicitly_allows_broad_changes(self):
        base = '# Report\nIntro.\n\n## Method\nOld.\n'
        candidate = '# New Report\nNew intro.\n\n## New Method\nNew method.\n'
        report = runtime.check_artifact_conformance(base, candidate, ['whole-artifact'])
        self.assertEqual(report['status'], 'pass')
        self.assertTrue(report['passed'])

    def test_provider_model_input_is_separate_from_audit_and_exclusions(self):
        source = self.ev('initial_brief', 'user', 'Preserve the recurring-maintenance thesis.')
        self.ev('assistant_turn', 'assistant', 'OLD PRIVATE HISTORY: do not inject this whole turn.')
        runtime.propose_branch(self.con, account=self.account, project=self.project, chat=self.chat,
            branch_id='bad-metaphor', label='Renewal from damage', tradeoff='Changes recurring process into a single event',
            strategy_key='wrong-metaphor')
        self.ev('generated_output', 'assistant', 'REJECTED DRAFT SECRET: renewal from damage',
            branch_id='bad-metaphor', inference_kind='generated_artifact')
        runtime.decide_branch(self.con, account=self.account, project=self.project, chat=self.chat,
            branch_id='bad-metaphor', status='rejected', note='Keep recurring maintenance, not a one-off recovery frame.')
        memory = runtime.add_memory(self.con, account=self.account, scope='account', tag='unreviewed',
            claim='UNRATIFIED MEMORY SECRET: should never be sent', source_event_seq=source['seq'])
        runtime.review_memory_claim(self.con, memory, 'accept')  # shared read-only reference, not keepable
        payload = runtime.hydrate_payload(self.con, account=self.account, project=self.project, chat=self.chat,
            recent_assistant_turns=0, relevance_tags={'unreviewed'})
        model_input, audit = runtime.build_model_input(payload, 'Continue from the stable thesis.', max_tokens=10000,
            token_counter=len)
        self.assertEqual(set(model_input.keys()), {'working_context', 'current_user_message'})
        serialized_model = json.dumps(model_input, ensure_ascii=False)
        self.assertIn('Continue from the stable thesis.', serialized_model)
        self.assertIn('Preserve the recurring-maintenance thesis.', serialized_model)
        self.assertNotIn('OLD PRIVATE HISTORY', serialized_model)
        self.assertNotIn('REJECTED DRAFT SECRET', serialized_model)
        self.assertNotIn('UNRATIFIED MEMORY SECRET', serialized_model)
        self.assertNotIn('omitted_events', model_input)
        self.assertNotIn('read_only_memory_ids_not_injected', model_input)
        self.assertNotIn('memory_id', model_input['working_context'])
        self.assertIn(memory, audit['read_only_memory_ids_not_injected'])
        self.assertIn('omitted_events', audit)
        self.assertNotIn('UNRATIFIED MEMORY SECRET', json.dumps(audit, ensure_ascii=False))
        self.assertEqual(audit['context_sha256'], __import__('hashlib').sha256(model_input['working_context'].encode()).hexdigest())

    def test_model_input_rejects_empty_current_user_message(self):
        payload = runtime.hydrate_payload(self.con, account=self.account, project=self.project, chat=self.chat)
        with self.assertRaises(ValueError):
            runtime.build_model_input(payload, '  ', max_tokens=10000, token_counter=len)


    def test_loopback_ollama_adapter_sends_allowlisted_input_without_a_token(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        captured = {}
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                captured['path'] = self.path
                size = int(self.headers.get('Content-Length', '0'))
                captured['body'] = json.loads(self.rfile.read(size).decode('utf-8'))
                response = json.dumps({'model':'mock-model','message':{'role':'assistant','content':'mock local response'},'done':True,'prompt_eval_count':12,'eval_count':4}).encode('utf-8')
                self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(response))); self.end_headers(); self.wfile.write(response)
            def log_message(self, *args):
                return
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            model_input={'working_context':"bounded context: preserve the user's original constraint",
                         'current_user_message':'continue the task'}
            result=runtime.ollama_chat(model_input,model='mock-model',base_url=f'http://127.0.0.1:{server.server_port}',timeout=5)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)
        self.assertEqual(captured['path'],'/api/chat')
        body=captured['body']
        self.assertEqual(set(body),{'model','messages','stream'})
        self.assertFalse(body['stream'])
        self.assertEqual(body['model'],'mock-model')
        self.assertEqual([x['role'] for x in body['messages']],['system','user'])
        serialized=json.dumps(body,ensure_ascii=False)
        self.assertIn('bounded context: preserve the user',serialized)
        self.assertIn('continue the task',serialized)
        self.assertNotIn('audit',serialized.casefold())
        self.assertNotIn('event_seq',serialized)
        self.assertEqual(result['content'],'mock local response')
        self.assertFalse(result['api_token_used'])
        self.assertEqual(result['provider'],'ollama-local')

    def test_ollama_adapter_refuses_non_loopback_hosts(self):
        with self.assertRaisesRegex(ValueError,'loopback'):
            runtime.ollama_chat({'working_context':'ctx','current_user_message':'query'},
                model='test-model',base_url='http://example.com:11434',timeout=1)
        with self.assertRaises(ValueError):
            runtime.ollama_chat({'working_context':'ctx','current_user_message':'query','audit':{}},
                model='test-model',base_url='http://127.0.0.1:11434',timeout=1)
        with self.assertRaisesRegex(ValueError, 'Cloud model names'):
            runtime.ollama_chat({'working_context':'ctx','current_user_message':'query'},
                model='some-model:cloud',base_url='http://127.0.0.1:11434',timeout=1)

    def test_ollama_adapter_rejects_malformed_response(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                size=int(self.headers.get('Content-Length','0')); self.rfile.read(size)
                body=b'{"model":"x","done":true}'
                self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
            def log_message(self,*args): return
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            with self.assertRaisesRegex(RuntimeError,'message.content'):
                runtime.ollama_chat({'working_context':'ctx','current_user_message':'query'},model='test',base_url=f'http://127.0.0.1:{server.server_port}',timeout=5)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)


    def test_ollama_cli_end_to_end_records_turn_and_keeps_audit_local(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        captured = {}
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                size = int(self.headers.get('Content-Length', '0'))
                captured['path'] = self.path
                captured['authorization'] = self.headers.get('Authorization')
                captured['body'] = json.loads(self.rfile.read(size).decode('utf-8'))
                body = json.dumps({
                    'model': 'mock-local-model',
                    'message': {'role': 'assistant', 'content': 'mock end-to-end answer'},
                    'done': True,
                    'prompt_eval_count': 24,
                    'eval_count': 7,
                }).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                return

        # Seed the persistent database, then exercise the actual runtime CLI against
        # a loopback mock implementing Ollama's /api/chat response contract.
        self.ev('initial_brief', 'user', 'Protect the original project constraint; ignore private audit details.')
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            response_path = self.root / 'response.json'
            audit_path = self.root / 'runtime-audit.json'
            cmd = [
                sys.executable, str(MODULE_PATH), '--db', str(self.root / 'test.sqlite3'),
                '--account', self.account, 'ollama-chat', '--project', self.project,
                '--chat', self.chat, '--current-user-message', 'Continue with the next useful step.',
                '--model', 'mock-local-model', '--endpoint', f'http://127.0.0.1:{server.server_port}',
                '--timeout', '5', '--max-tokens', '12000', '--out', str(response_path),
                '--audit-out', str(audit_path),
            ]
            completed = subprocess.run(cmd, text=True, capture_output=True, timeout=15)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(captured['path'], '/api/chat')
        self.assertIsNone(captured['authorization'], 'local inference must not send an Authorization header')
        request_body = captured['body']
        self.assertEqual(set(request_body), {'model', 'messages', 'stream'})
        self.assertFalse(request_body['stream'])
        serialized = json.dumps(request_body, ensure_ascii=False)
        self.assertIn('Protect the original project constraint', serialized)
        self.assertIn('Continue with the next useful step', serialized)
        self.assertNotIn('runtime-audit', serialized)
        self.assertNotIn('included_event_seqs', serialized)
        self.assertNotIn('context_sha256', serialized)

        answer = json.loads(response_path.read_text(encoding='utf-8'))
        audit = json.loads(audit_path.read_text(encoding='utf-8'))
        self.assertEqual(answer['content'], 'mock end-to-end answer')
        self.assertEqual(answer['provider'], 'ollama-local')
        self.assertFalse(audit['api_token_used'])
        self.assertNotEqual(response_path.resolve(), audit_path.resolve())
        self.assertEqual(audit['call_status'], 'success')

        # A fresh DB connection sees both turns in the persistent ledger.
        verify = runtime.connect(self.root / 'test.sqlite3')
        try:
            contents = [r['content'] for r in runtime.scope_events(verify, self.account, self.project, self.chat)]
            self.assertIn('Continue with the next useful step.', contents)
            self.assertIn('mock end-to-end answer', contents)
        finally:
            verify.close()


    def test_model_and_audit_outputs_must_resolve_to_distinct_paths(self):
        good_model, good_audit = runtime.ensure_distinct_output_paths(self.root / 'model.json', self.root / 'audit.json')
        self.assertNotEqual(good_model, good_audit)
        with self.assertRaisesRegex(ValueError, 'different file paths'):
            runtime.ensure_distinct_output_paths(self.root / 'same.json', self.root / '.' / 'same.json')


    def test_file_backed_revision_pins_exact_source_bytes_and_reloads_files(self):
        import hashlib, json
        workspace = self.root / "revision-workspace"
        workspace.mkdir()
        base_bytes = b"# Report\r\nOriginal.\r\n"
        output_bytes = b"# Report\r\nRevised.\r\n"
        (workspace / "report.md").write_bytes(base_bytes)
        (workspace / "expanded.md").write_bytes(output_bytes)
        preview = runtime.propose_revision_from_file(
            self.con, workspace_root=workspace, artifact_file="report.md",
            account=self.account, project=self.project, chat=self.chat, proposal_id="rev-file-backed",
            base_version="v1", original_request="Revise this report.",
            delta_summary="Update the report text.", impact_summary="The report section changes.",
            changed_sections=["heading:Report"])
        self.assertEqual(preview["base_sha256"], hashlib.sha256(base_bytes).hexdigest())
        self.assertEqual(preview["source_ref"], "report.md")
        self.assertTrue(preview["source_artifact"]["loaded_by_runtime"])
        runtime.decide_revision(self.con, "rev-file-backed", "accept", account=self.account,
            project=self.project, chat=self.chat)
        expanded = runtime.expand_revision_from_file(
            self.con, "rev-file-backed", workspace_root=workspace, artifact_version="v2",
            content_file="expanded.md", account=self.account, project=self.project, chat=self.chat)
        self.assertEqual(expanded["expanded_content_file_sha256"], hashlib.sha256(output_bytes).hexdigest())
        history = runtime.revision_history(self.con, "rev-file-backed", account=self.account,
            project=self.project, chat=self.chat)
        expand_event = next(e for e in history if e["event_type"] == "revision.expanded")
        self.assertEqual(json.loads(expand_event["metadata_json"])["content_source_ref"], "expanded.md")
        report = runtime.verify_revision_output_from_file(
            self.con, "rev-file-backed", workspace_root=workspace,
            account=self.account, project=self.project, chat=self.chat)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["base_source_ref"], "report.md")
        self.assertTrue(report["base_source_loaded_by_runtime"])


    def test_file_backed_expansion_refuses_source_changed_after_proposal(self):
        workspace = self.root / "revision-workspace"
        workspace.mkdir()
        (workspace / "report.md").write_text("# Report\nOriginal.\n", encoding="utf-8")
        (workspace / "expanded.md").write_text("# Report\nRevised.\n", encoding="utf-8")
        runtime.propose_revision_from_file(
            self.con, workspace_root=workspace, artifact_file="report.md",
            account=self.account, project=self.project, chat=self.chat, proposal_id="rev-file-stale",
            base_version="v1", original_request="Revise this report.",
            delta_summary="Update the report text.", impact_summary="The report section changes.",
            changed_sections=["heading:Report"])
        runtime.decide_revision(self.con, "rev-file-stale", "accept", account=self.account,
            project=self.project, chat=self.chat)
        (workspace / "report.md").write_text("# Report\nChanged out of band.\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed after delta review"):
            runtime.expand_revision_from_file(
                self.con, "rev-file-stale", workspace_root=workspace, artifact_version="v2",
                content_file="expanded.md", account=self.account, project=self.project, chat=self.chat)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM revision_outputs WHERE proposal_id='rev-file-stale'").fetchone()[0], 0)


    def test_file_loader_rejects_parent_and_symlink_escapes(self):
        workspace = self.root / "revision-workspace"
        workspace.mkdir()
        outside = self.root / "outside.md"
        outside.write_text("# Outside", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "absolute paths and '..'"):
            runtime.read_workspace_artifact(workspace, "../outside.md")
        escape = workspace / "escape.md"
        try:
            escape.symlink_to(outside)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Symlink creation is unavailable in this environment: {exc}")
        with self.assertRaisesRegex(ValueError, "outside or not relative"):
            runtime.read_workspace_artifact(workspace, "escape.md")


    def test_file_backed_verification_reloads_changed_source_and_fails_closed(self):
        workspace = self.root / "revision-workspace"
        workspace.mkdir()
        (workspace / "report.md").write_text("# Report\nOriginal.\n", encoding="utf-8")
        (workspace / "expanded.md").write_text("# Report\nRevised.\n", encoding="utf-8")
        runtime.propose_revision_from_file(
            self.con, workspace_root=workspace, artifact_file="report.md",
            account=self.account, project=self.project, chat=self.chat, proposal_id="rev-verify-file-stale",
            base_version="v1", original_request="Revise this report.",
            delta_summary="Update the report text.", impact_summary="The report section changes.",
            changed_sections=["heading:Report"])
        runtime.decide_revision(self.con, "rev-verify-file-stale", "accept", account=self.account,
            project=self.project, chat=self.chat)
        runtime.expand_revision_from_file(
            self.con, "rev-verify-file-stale", workspace_root=workspace, artifact_version="v2",
            content_file="expanded.md", account=self.account, project=self.project, chat=self.chat)
        (workspace / "report.md").write_text("# Report\nExternally changed after expansion.\n", encoding="utf-8")
        report = runtime.verify_revision_output_from_file(
            self.con, "rev-verify-file-stale", workspace_root=workspace,
            account=self.account, project=self.project, chat=self.chat)
        self.assertEqual(report["status"], "fail")
        self.assertFalse(report["ready_for_release"])
        self.assertEqual(report["base_source_ref"], "report.md")
        self.assertEqual(runtime._revision_state(self.con, "rev-verify-file-stale"), "rejected_reset")


    def test_revision_cli_advertises_path_rooted_commands(self):
        result = subprocess.run([sys.executable, str(RUNTIME_PATH), "revision", "--help"],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("propose-file", result.stdout)
        self.assertIn("expand-file", result.stdout)
        self.assertIn("verify-file", result.stdout)


if __name__ == '__main__': unittest.main()
