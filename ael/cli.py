"""Command-line interface for the modular AEL runtime."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from .config import *
from .database import *
from .ledger import *
from .branches import *
from .memory import *
from .context import *
from .provider import *
from .sessions import *
from .checkpoints import *
from .revisions import *
from .paths import *

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', default=str(default_data_dir() / 'ael.sqlite3'))
    p.add_argument('--account', default='default')
    sub = p.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('record'); r.add_argument('--project', required=True); r.add_argument('--chat', required=True); r.add_argument('--type', dest='event_type', required=True); r.add_argument('--provenance', choices=sorted(VALID_PROVENANCE), required=True); r.add_argument('--content', required=True); r.add_argument('--authority', choices=sorted(VALID_AUTHORITIES), default='none'); r.add_argument('--inference-kind', choices=sorted(VALID_INFERENCE_KINDS), default='unspecified'); r.add_argument('--truth-status', choices=sorted(VALID_TRUTH_STATUSES), default='unverified'); r.add_argument('--source-ref'); r.add_argument('--branch'); r.add_argument('--strategy-key'); r.add_argument('--metadata', default='{}')
    g = sub.add_parser('gate'); g.add_argument('--project', required=True); g.add_argument('--chat', required=True); g.add_argument('--decision', choices=['single','clarify','branch','recommend','just_pick','branch_it'], required=True); g.add_argument('--original-query')
    b = sub.add_parser('branch'); b.add_argument('--project', required=True); b.add_argument('--chat', required=True); b.add_argument('--id', required=True); b.add_argument('--label', required=True); b.add_argument('--tradeoff', required=True); b.add_argument('--strategy-key', required=True); b.add_argument('--original-query')
    d = sub.add_parser('decide'); d.add_argument('--project', required=True); d.add_argument('--chat', required=True); d.add_argument('--id', required=True); d.add_argument('--status', choices=['selected','rejected','completed'], required=True); d.add_argument('--note', default=''); d.add_argument('--decision-path', choices=['direct','accepted_recommendation','system'], default='direct'); d.add_argument('--strategy-failure', action='store_true'); d.add_argument('--threshold', type=int, default=3); d.add_argument('--usage-status', choices=sorted(BRANCH_REUSE_STATUSES), default='not_pertinent_now')
    h = sub.add_parser('hydrate'); h.add_argument('--project', required=True); h.add_argument('--chat', required=True); h.add_argument('--relevance-tags', nargs='*', help='Explicit tags relevant to this task')
    mc = sub.add_parser('model-context'); mc.add_argument('--project', required=True); mc.add_argument('--chat', required=True); mc.add_argument('--max-tokens', type=int, default=12000); mc.add_argument('--recent-assistant-turns', type=int, default=6); mc.add_argument('--relevance-tags', nargs='*', help='Tags/strategy keys applicable to this task')
    mi = sub.add_parser('model-input'); mi.add_argument('--project', required=True); mi.add_argument('--chat', required=True); mi.add_argument('--current-user-message', required=True); mi.add_argument('--max-tokens', type=int, default=12000); mi.add_argument('--recent-assistant-turns', type=int, default=6); mi.add_argument('--relevance-tags', nargs='*', help='Explicitly applicable memory tags'); mi.add_argument('--out', required=True); mi.add_argument('--audit-out', required=True)
    oc = sub.add_parser('ollama-chat', help='Send the allowlisted active context to a loopback-only local Ollama model; no API key'); oc.add_argument('--project', required=True); oc.add_argument('--chat', required=True); oc.add_argument('--current-user-message', required=True); oc.add_argument('--model', required=True); oc.add_argument('--endpoint', default='http://127.0.0.1:11434'); oc.add_argument('--timeout', type=float, default=120.0); oc.add_argument('--max-tokens', type=int, default=12000); oc.add_argument('--recent-assistant-turns', type=int, default=6); oc.add_argument('--relevance-tags', nargs='*', help='Explicitly applicable memory tags'); oc.add_argument('--out', required=True); oc.add_argument('--audit-out', required=True)
    os = sub.add_parser('ollama-status', help='Check a loopback Ollama service and list locally available models; no prompt is sent'); os.add_argument('--endpoint', default='http://127.0.0.1:11434'); os.add_argument('--timeout', type=float, default=3.0)
    c = sub.add_parser('checkpoint'); c.add_argument('--project', required=True); c.add_argument('--chat', required=True); c.add_argument('--out', default='handoffs')
    m = sub.add_parser('memory'); ms = m.add_subparsers(dest='memory_cmd', required=True)
    mp = ms.add_parser('propose'); mp.add_argument('--scope', choices=['account','project'], required=True); mp.add_argument('--project'); mp.add_argument('--tag', required=True); mp.add_argument('--claim', required=True); mp.add_argument('--source-event-seq', type=int); mp.add_argument('--weight', type=float, default=1.0)
    mr = ms.add_parser('review'); mr.add_argument('--id', required=True); mr.add_argument('--decision', choices=['accept','edit','reject'], required=True); mr.add_argument('--claim'); mr.add_argument('--note', default='')
    mre = ms.add_parser('reopen'); mre.add_argument('--id', required=True); mre.add_argument('--note', default='')
    mres = ms.add_parser('resolve'); mres.add_argument('--id', required=True); mres.add_argument('--decision', choices=['use','avoid','later','not_pertinent_now','keep'], required=True); mres.add_argument('--note', default='')
    mrb = ms.add_parser('batch-resolve'); mrb.add_argument('--ids', nargs='+', required=True); mrb.add_argument('--decision', choices=['use','avoid','later','not_pertinent_now','keep'], required=True); mrb.add_argument('--note', default='')
    mu = ms.add_parser('set-usage'); mu.add_argument('--id', required=True); mu.add_argument('--status', choices=sorted(VALID_USAGE_STATUSES), required=True); mu.add_argument('--note', default='')
    ma = ms.add_parser('set-state'); ma.add_argument('--id', required=True); ma.add_argument('--action', choices=['ratify','dormant','reverse','reactivate','confirm'], required=True); ma.add_argument('--note', default='')
    ml = ms.add_parser('list'); ml.add_argument('--project'); ml.add_argument('--tag'); ml.add_argument('--include-local', action='store_true'); ml.add_argument('--include-discarded', action='store_true')
    rv = sub.add_parser('revision'); rvs = rv.add_subparsers(dest='revision_cmd', required=True)
    rvp = rvs.add_parser('propose'); rvp.add_argument('--project', required=True); rvp.add_argument('--chat', required=True); rvp.add_argument('--id', required=True); rvp.add_argument('--artifact-id', required=True); rvp.add_argument('--base-version', required=True); rvp.add_argument('--original-request', required=True); rvp.add_argument('--delta-summary', required=True); rvp.add_argument('--impact-summary', required=True); rvp.add_argument('--changed-section', nargs='+', required=True); rvp.add_argument('--base-sha256'); rvp.add_argument('--source-ref')
    rvsw = rvs.add_parser('show'); rvsw.add_argument('--id', required=True)
    rvh = rvs.add_parser('history'); rvh.add_argument('--id', required=True)
    rvd = rvs.add_parser('decide'); rvd.add_argument('--id', required=True); rvd.add_argument('--decision', choices=['accept','reject'], required=True); rvd.add_argument('--note', default='')
    rvr = rvs.add_parser('replan'); rvr.add_argument('--project', required=True); rvr.add_argument('--chat', required=True); rvr.add_argument('--from-id', required=True); rvr.add_argument('--id', required=True); rvr.add_argument('--delta-summary', required=True); rvr.add_argument('--impact-summary', required=True); rvr.add_argument('--changed-section', nargs='+', required=True); rvr.add_argument('--base-version'); rvr.add_argument('--base-sha256'); rvr.add_argument('--source-ref')
    rvc = rvs.add_parser('replan-context'); rvc.add_argument('--id', required=True); rvc.add_argument('--project', required=True); rvc.add_argument('--chat', required=True)
    rve = rvs.add_parser('expand'); rve.add_argument('--id', required=True); rve.add_argument('--artifact-version', required=True); rve.add_argument('--content-file', required=True); rve.add_argument('--current-base-sha256', help='Required at expansion if the proposal pinned --base-sha256')
    rvo = rvs.add_parser('get-output'); rvo.add_argument('--id', required=True); rvo.add_argument('--out', required=True); rvo.add_argument('--allow-unverified', action='store_true', help='Explicitly export an output that has not passed conformance; not recommended')
    rvv = rvs.add_parser('verify-output'); rvv.add_argument('--id', required=True); rvv.add_argument('--base-file', required=True); rvv.add_argument('--report-out')
    rvvh = rvs.add_parser('verification-history'); rvvh.add_argument('--id', required=True)
    a = p.parse_args()
    if a.cmd == 'ollama-status':
      status = ollama_status(a.endpoint, timeout=a.timeout)
      print(json.dumps(status, ensure_ascii=False, indent=2))
      return 0 if status.get('available') else 2
    con = connect(a.db)
    try:
      if a.cmd == 'record':
        e=append_event(con, account=a.account, project=a.project, chat=a.chat, event_type=a.event_type, provenance=a.provenance, content=a.content,
          authority=a.authority, inference_kind=a.inference_kind, truth_status=a.truth_status, source_ref=a.source_ref,
          branch_id=a.branch, strategy_key=a.strategy_key, metadata=json.loads(a.metadata))
        print(json.dumps({'recorded': True, 'seq': e['seq'], 'event_id': e['event_id']}, indent=2))
      elif a.cmd == 'gate':
        if a.original_query and not con.execute(
          "SELECT 1 FROM events WHERE account_id=? AND project_id=? AND chat_id=? AND event_type='original_query' LIMIT 1",
          (a.account,a.project,a.chat)).fetchone():
          append_event(con,account=a.account,project=a.project,chat=a.chat,event_type='original_query',provenance='user',
            authority='user_direct',inference_kind='user_statement',truth_status='not_applicable',content=a.original_query)
        result=gate_message(a.decision)
        append_event(con,account=a.account,project=a.project,chat=a.chat,event_type='materiality_gate.override' if a.decision in {'just_pick','branch_it'} else 'materiality_gate.assessed',
          provenance='user' if a.decision in {'just_pick','branch_it'} else 'system',authority='user_direct' if a.decision in {'just_pick','branch_it'} else 'system_process',
          inference_kind='process_event',truth_status='not_applicable',content=result['message'],metadata={'decision':a.decision,'original_query':a.original_query})
        print(json.dumps(result, indent=2))
      elif a.cmd == 'branch':
        propose_branch(con, account=a.account, project=a.project, chat=a.chat, branch_id=a.id, label=a.label,
          tradeoff=a.tradeoff, strategy_key=a.strategy_key, original_query=a.original_query)
        print(f'Proposed branch {a.id}: {a.label}; trade-off: {a.tradeoff}')
      elif a.cmd == 'decide':
        result=decide_branch(con, account=a.account, project=a.project, chat=a.chat, branch_id=a.id, status=a.status,
          note=a.note, decision_path=a.decision_path, strategy_failure=a.strategy_failure, threshold=a.threshold, usage_status=a.usage_status)
        print(json.dumps({'branch_id':a.id,'status':a.status,'circuit_breaker':result}, indent=2))
      elif a.cmd == 'hydrate':
        print(render_markdown(hydrate_payload(con, account=a.account, project=a.project, chat=a.chat, relevance_tags=set(a.relevance_tags) if a.relevance_tags is not None else None)))
      elif a.cmd == 'model-context':
        payload=hydrate_payload(con,account=a.account,project=a.project,chat=a.chat,recent_assistant_turns=a.recent_assistant_turns,relevance_tags=set(a.relevance_tags) if a.relevance_tags is not None else None)
        packed=render_model_context(payload,max_tokens=a.max_tokens)
        print(json.dumps(packed,ensure_ascii=False,indent=2))
      elif a.cmd == 'model-input':
        ensure_distinct_output_paths(a.out, a.audit_out)
        payload=hydrate_payload(con,account=a.account,project=a.project,chat=a.chat,recent_assistant_turns=a.recent_assistant_turns,relevance_tags=set(a.relevance_tags) if a.relevance_tags is not None else None)
        model_input, audit = build_model_input(payload,a.current_user_message,max_tokens=a.max_tokens)
        out, audit_out = ensure_distinct_output_paths(a.out, a.audit_out); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(model_input,ensure_ascii=False,indent=2),encoding='utf-8')
        audit_out.parent.mkdir(parents=True,exist_ok=True); audit_out.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'model_input_path':str(out),'audit_path':str(audit_out),'model_input_keys':sorted(model_input.keys()),'audit_separate':out.resolve()!=audit_out.resolve()},indent=2))
      elif a.cmd == 'ollama-chat':
        ensure_distinct_output_paths(a.out, a.audit_out)
        # Hydrate and pack before adding the current query to history; this prevents duplicating it in the context.
        payload=hydrate_payload(con,account=a.account,project=a.project,chat=a.chat,recent_assistant_turns=a.recent_assistant_turns,relevance_tags=set(a.relevance_tags) if a.relevance_tags is not None else None)
        # Reserve a rough estimate for the adapter's fixed system prompt, delimiters and current user message.
        reserve_text=OLLAMA_SYSTEM_PROMPT + a.current_user_message + '=== BOUNDED WORKING CONTEXT === === CURRENT USER MESSAGE ==='
        reserved=rough_token_estimate(reserve_text)
        model_input, audit = build_model_input(payload,a.current_user_message,max_tokens=a.max_tokens,reserved_tokens=reserved)
        user_event=append_event(con,account=a.account,project=a.project,chat=a.chat,event_type='user_request',provenance='user',authority='user_direct',inference_kind='user_statement',truth_status='not_applicable',content=a.current_user_message,metadata={'context_sha256':audit['context_sha256'],'model':a.model,'transport':'ollama-local'})
        try:
          response=ollama_chat(model_input,model=a.model,base_url=a.endpoint,timeout=a.timeout)
        except Exception as exc:
          audit.update({'provider':'ollama-local','model':a.model,'call_status':'failed','failure_type':type(exc).__name__,
                        'api_token_used':False,'user_event_seq':user_event['seq']})
          out_path, audit_out = ensure_distinct_output_paths(a.out, a.audit_out); audit_out.parent.mkdir(parents=True,exist_ok=True); audit_out.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
          raise
        assistant_event=append_event(con,account=a.account,project=a.project,chat=a.chat,event_type='assistant_turn',provenance='assistant',authority='none',inference_kind='inference',truth_status='unverified',source_ref=f"ollama:{response['model']}",content=response['content'],metadata={'context_sha256':audit['context_sha256'],'in_reply_to_seq':user_event['seq'],'model':response['model'],'metrics':response['metrics']})
        audit.update({'provider':'ollama-local','model':response['model'],'endpoint_host':response['endpoint_host'],'api_token_used':False,'call_status':'success','user_event_seq':user_event['seq'],'assistant_event_seq':assistant_event['seq'],'token_counter_warning':'The active context budget uses the offline estimate unless a provider-specific counter is injected.'})
        out, audit_out = ensure_distinct_output_paths(a.out, a.audit_out); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps({'provider':response['provider'],'model':response['model'],'content':response['content'],'done':response['done'],'metrics':response['metrics'],'user_event_seq':user_event['seq'],'assistant_event_seq':assistant_event['seq']},ensure_ascii=False,indent=2),encoding='utf-8')
        audit_out.parent.mkdir(parents=True,exist_ok=True); audit_out.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'response_path':str(out),'audit_path':str(audit_out),'provider':'ollama-local','model':response['model'],'api_token_used':False,'audit_separate':out.resolve()!=audit_out.resolve()},indent=2))
      elif a.cmd == 'checkpoint':
        md,js=checkpoint(con,account=a.account,project=a.project,chat=a.chat,out_dir=a.out)
        print(json.dumps({'markdown':str(md),'json':str(js),'verified':md.is_file() and json.loads(js.read_text(encoding='utf-8'))['schema_version']==2},indent=2))
      elif a.cmd == 'memory':
        if a.memory_cmd == 'propose':
          mid=add_memory(con,account=a.account,scope=a.scope,tag=a.tag,claim=a.claim,project=a.project,source_event_seq=a.source_event_seq,weight=a.weight)
          print(json.dumps({'memory_id':mid,'state':'pending','stage':'local_candidate','next_step':f'memory review --id {mid} --decision accept|edit|reject','influence_permission':False},indent=2))
        elif a.memory_cmd == 'review':
          result=review_memory_claim(con,a.id,a.decision,edited_claim=a.claim,note=a.note); print(json.dumps(result,ensure_ascii=False,indent=2))
        elif a.memory_cmd == 'reopen':
          result=reopen_memory_candidate(con,a.id,note=a.note); print(json.dumps(result,ensure_ascii=False,indent=2))
        elif a.memory_cmd == 'resolve':
          result=resolve_memory_reference(con,a.id,a.decision,note=a.note); print(json.dumps(result,ensure_ascii=False,indent=2))
        elif a.memory_cmd == 'batch-resolve':
          result=resolve_memory_batch(con,a.ids,a.decision,note=a.note); print(json.dumps(result,ensure_ascii=False,indent=2))
        elif a.memory_cmd == 'set-state':
          change_memory_state(con,a.id,a.action,note=a.note); print(json.dumps({'memory_id':a.id,'action':a.action,'updated':True},indent=2))
        elif a.memory_cmd == 'set-usage':
          result=set_memory_usage_status(con,a.id,a.status,note=a.note); print(json.dumps(result,ensure_ascii=False,indent=2))
        else:
          print(json.dumps(list_memories(con,account=a.account,project=a.project,tag=a.tag,include_local=a.include_local,include_discarded=a.include_discarded),ensure_ascii=False,indent=2))
      elif a.cmd == 'revision':
        if a.revision_cmd == 'propose':
          result = propose_revision(con, account=a.account, project=a.project, chat=a.chat, proposal_id=a.id,
            artifact_id=a.artifact_id, base_version=a.base_version, original_request=a.original_request,
            delta_summary=a.delta_summary, impact_summary=a.impact_summary, changed_sections=a.changed_section,
            base_sha256=a.base_sha256, source_ref=a.source_ref)
          print(json.dumps(result, ensure_ascii=False, indent=2))
        elif a.revision_cmd == 'show':
          print(json.dumps(revision_preview(con, a.id, account=a.account), ensure_ascii=False, indent=2))
        elif a.revision_cmd == 'history':
          print(json.dumps(revision_history(con, a.id, account=a.account), ensure_ascii=False, indent=2))
        elif a.revision_cmd == 'decide':
          print(json.dumps(decide_revision(con, a.id, a.decision, note=a.note, account=a.account), ensure_ascii=False, indent=2))
        elif a.revision_cmd == 'replan':
          parent = _get_revision(con, a.from_id, account=a.account, project=a.project, chat=a.chat)
          result = propose_revision(con, account=a.account, project=a.project, chat=a.chat, proposal_id=a.id,
            artifact_id=parent['artifact_id'], base_version=a.base_version or parent['base_version'],
            original_request=parent['original_request'], delta_summary=a.delta_summary,
            impact_summary=a.impact_summary, changed_sections=a.changed_section,
            base_sha256=a.base_sha256, source_ref=a.source_ref, parent_revision_id=a.from_id)
          print(json.dumps(result, ensure_ascii=False, indent=2))
        elif a.revision_cmd == 'replan-context':
          print(json.dumps(revision_replan_context(con, a.id, account=a.account, project=a.project, chat=a.chat), ensure_ascii=False, indent=2))
        elif a.revision_cmd == 'expand':
          content = Path(a.content_file).read_text(encoding='utf-8')
          print(json.dumps(expand_revision(con, a.id, artifact_version=a.artifact_version, content=content, account=a.account, current_base_sha256=a.current_base_sha256), ensure_ascii=False, indent=2))
        elif a.revision_cmd == 'verify-output':
          base = Path(a.base_file).read_text(encoding='utf-8')
          report = verify_revision_output(con,a.id,base_content=base,account=a.account)
          if a.report_out:
            report_path=Path(a.report_out); report_path.parent.mkdir(parents=True,exist_ok=True); report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
          print(json.dumps(report,ensure_ascii=False,indent=2))
        elif a.revision_cmd == 'verification-history':
          print(json.dumps(revision_conformance_history(con,a.id),ensure_ascii=False,indent=2))
        else:
          result = revision_output(con, a.id)
          if not result['ready_for_release'] and not a.allow_unverified:
            raise ValueError(f"Output is not ready for release (conformance_status={result['conformance_status']!r}). Run revision verify-output with the exact base file, or use --allow-unverified only for explicit inspection.")
          out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(result['content'], encoding='utf-8')
          print(json.dumps({'output_id': result['output_id'], 'out': str(out), 'artifact_version': result['artifact_version'], 'content_sha256': result['content_sha256'], 'conformance_status':result['conformance_status'],'ready_for_release':result['ready_for_release'],'verified': out.is_file()}, ensure_ascii=False, indent=2))
    finally:
      con.close()

if __name__ == '__main__':
    raise SystemExit(main())


if __name__ == "__main__":
    main()
