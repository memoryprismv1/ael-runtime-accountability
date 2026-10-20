# AEL V1 Evidence Pack — Source Reconciliation

**Purpose:** Record what the supplied Evidence Pack adds to the already-read AEL Runtime V1 document and Design Notes. This is an implementation audit, not a replacement or reinterpretation of the author's framework.

## 1. Source role

The Evidence Pack describes itself as the evidence layer: authorship, the concrete failure that generated a mechanism, and external corroborating material. It explicitly says it is not a rewrite of the essays or a summary/replacement of the specified mechanisms. Accordingly:

- The AEL essays remain the conceptual source corpus.
- The Runtime Accountability V1 document presents the runtime architecture.
- The Design Notes carry the working object model and mechanism details.
- The Evidence Pack records origins, evidence, and the source's own status distinctions.
- Code and audits remain subordinate implementation artifacts.

## 2. Authorship and provenance

The Evidence Pack states: the user created the architecture; AI systems were reviewers and stress-testers. The prototype must not reverse that order or claim authorship of AEL.

The motivating incident is the image-generation session where the system pursued a one-time "renewal from damage" interpretation instead of continuous recurring maintenance. Multiple recovery exchanges were required because the rejected frame continued to influence the active context. The general mechanism is context pollution/anchoring, not the domain of that one image.

## 3. Evidence-pack status distinctions to preserve

The Evidence Pack labels these mechanisms/object-model elements as load-bearing and pressure-tested: 0–3, 8, 10, 11, and the object model. Mechanism 4 is described as real/existing. Mechanism 5 (locale tags and residual fallback) is explicitly a hypothesis not yet pressure-tested. The read/influence split added to Mechanism 6 is a targeted extension deliberately kept small. V2 documents must preserve these unequal statuses rather than present every element as equally settled.

## 4. Corrected interpretation of Mechanism 8, Part B

The Evidence Pack explicitly corrects the too-simple axis "user content = evidence, AI content = guess". Keep four distinct questions:

- **Provenance:** who said or supplied X?
- **Decision authority:** who chose or ratified X?
- **Truth status:** is X externally verified as true?
- **Inference kind:** is X a statement, observation, hypothesis, inference, or generated artifact?

It also resolves an ambiguity about old assistant turns. Aged assistant turns are retained verbatim as historical artifacts but stop being fed back into active context by default. They are not summarized into a new claim by the same model. This is a key constraint for V2. The runtime's recent-turn window is a parameter chosen for the prototype; the evidence pack does not prescribe the exact numerical threshold.

## 5. External evidence boundary

The pack deliberately keeps external evidence separate from the architecture's origin. It maps NIST material to human-AI role separation and the Materiality Gate; automation-bias studies to meaningful trade-offs and ratification; long-context research to the limited claim that more context is not equally usable; and legal precedents to the narrower observation that responsibility must be located within AI-mediated decision chains. It explicitly cautions against claiming those sources directly prove the specific AEL mechanisms.

## 6. Implementation implications

- Keep all history immutable; construct active context as a projection.
- Reset by discarding and rehydrating the local context object, not by telling the model to forget.
- Keep rejected output out of the active projection while retaining the rejection decision/reason.
- Keep AI-originated old output retrievable but not active by default; do not silently compress it into a claim.
- Keep memory readable distinct from memory allowed to influence current decisions.
- Expose meaningful choices and trade-offs without making all requests go through a branching ritual.
- Keep humans in charge of consequential decisions and memory promotion.
- Do not promote architecture hypotheses to implemented or validated facts.

## 7. Validation boundary

The V2 unit tests establish behavior for implemented primitives only. They do not prove the architecture as a whole, validate the external evidence claims, or demonstrate integration with a model. The mechanism alignment table remains the source of truth for implementation status.


## 8. V2.5 — retention versus use

A later user clarification sharpened how learning from outcomes should inform this implementation: **keep the data irrespective of the immediate outcome; govern use by applicability.** The user's formulation distinguishes useful, never try again, maybe later, and not pertinent now. This maps naturally to a difference between the historical record and the current-context projection.

The code now records a usage disposition separately from memory lifecycle stage and influence permission. A status is not a truth claim. `never_try_again` is not inferred from every rejection; it must be chosen explicitly. `maybe_later` and `not_pertinent_now` remain retrievable but are not injected into the active model context. Conditional memories require explicit matching tags; no automatic semantic relevance classifier is claimed.

The same clarification tightened Materiality Gate behavior. The word “Lancet” is used as an example of low-cost ambiguity: infer from surrounding context where possible, otherwise ask one concise clarifying question. Formal branch exposure is reserved for a choice that materially determines what happens next. This is a calibration example for Mechanism 0, not an additional AEL mechanism or a domain-specific subproject.

These are implementation interpretations motivated by the user's own *Learning the World Through Others* framing; they do not claim that the exact status enum or runtime code appears verbatim in that source.
