# First-week plan

Status: proposed, not completed by the group. Start with three working sessions and adapt their dates when the deadline is known.

## Purpose

Show the teacher how the project develops by preserving evidence as work happens: initial needs, decisions and alternatives, evolving diagrams, reviewed tasks, and eventually test results. Record real dates and contributions.

The assessment assigns 15% to framing, 25% to design and standards, 25% to implementation, 15% to validation, 10% to security/confidentiality/compliance, and 10% to reporting/presentation (assignment page 15).

## Proposed scope to discuss

One fictional outpatient facility with a laboratory and radiology service. A clinician opens one synthetic patient record and consults laboratory results, a radiology report, and associated imaging.

Candidate actors: registration clerk, laboratory technician, radiology staff, and clinician. Agree who enters, validates, and views each record.

An eventual demonstration follows one patient from registration through laboratory and radiology requests to combined consultation. A proposed degraded case is a laboratory message with an unknown patient identifier: reject or hold it for review without attaching it to another patient. Agree the exact behavior in requirements work.

## Lifecycle overview

| Phase | Evidence to preserve | Status |
| --- | --- | --- |
| Initiation and preparation | Scope, responsibilities, meeting notes, tool checks | Current phase |
| Requirements | Actors, patient journey, numbered requirements and acceptance criteria | Later |
| Design | Relational model, architecture, standards mapping, decision records | Later |
| Implementation | Small changes, reviews, runnable increments, configuration | Later |
| Validation | Complete scenario, degraded case, numerical results and limitations | Later |
| Delivery and review | Setup guide, technical report, demo, oral presentation | Later |

Revisit earlier decisions when trials or tests reveal problems, and record why they changed. The teacher's required development method remains unknown.

## Session 1: kickoff, 60-90 minutes

- Read assignment pages 3-4, 10, 14, and 15 together.
- Confirm deadline, required method, report language, and imposed tools.
- Agree a fictional care setting, problem, actors, and one patient journey.
- Assign names to the six responsibilities and reviewers below.
- Review the Python stack proposal and record uncertainties.
- Save dated notes using the meeting template.

**Done when:** the group has reviewed a short scope and responsibility table, with open questions recorded. These starter drafts do not mean a meeting has happened.

## Session 2: prepare the tools, 60-90 minutes

- Each member follows the basic software checklist.
- Record OS, versions, successful checks, and blockers.
- Verify everyone can open and edit the chosen diagram format.
- Identify owners for later Streamlit and Orthanc trials.
- Draft tasks locally. Set up GitHub issues and a board in a later collaboration step.

**Done when:** all six readiness entries contain actual results and each blocker has an owner.

## Session 3: requirements workshop, about 90 minutes

- Sketch the patient journey, actors, and handoffs.
- Draft five to eight requirements with observable acceptance criteria.
- Identify the shared patient identifier and cross-system association rules.
- List candidate entities for design: patient, laboratory order/result, radiology order/report, and imaging study reference.
- List HL7 v2 message/profile and DICOM field questions to investigate.
- Choose a degraded case and a measurable outcome, such as correct patient/result association rate on a documented synthetic test set. Agree targets before testing and record results only after tests run.

**Done when:** a workflow sketch, requirements draft, standards questions, and validation ideas have been reviewed.

## Six-person responsibility proposal

These are starting responsibilities, not permanent silos. Everyone later contributes to implementation, review, and the report.

| Member | Responsibility | First output | Reviewer |
| --- | --- | --- | --- |
| 1: TBD | Coordination and care context | Kickoff notes and scope | Member 6 |
| 2: TBD | Data modeling | Candidate entities and identifier questions | Member 3 |
| 3: TBD | Laboratory and HL7 v2 | Laboratory workflow and message questions | Member 2 |
| 4: TBD | Imaging, Orthanc, DICOM | Imaging workflow and trial checklist | Member 5 |
| 5: TBD | Interface and radiology workflow | Paper sketch of combined patient view | Member 4 |
| 6: TBD | Validation and security | Acceptance criteria, degraded case, data-origin checklist | Member 1 |

End each meeting with a brief explanation of each member's findings. The assignment requires every member to answer questions about the whole project.

## Initial tasks

All tasks below are **To do**, pending actual team work. Owners refer to the proposed roles.

| ID | Task | Owner | Completion evidence |
| --- | --- | --- | --- |
| INIT-01 | Confirm deadline and constraints | 1 | Answers in meeting notes |
| INIT-02 | Agree care setting and scope | 1 | Scope reviewed by all six |
| INIT-03 | Verify development tools | Each member, coordinated by 6 | Six actual readiness records |
| INIT-04 | Sketch patient journey | 5 with 3 and 4 | Actors, handoffs, shared record visible |
| INIT-05 | Identify records and identifiers | 2 | Reviewed candidate entities and linking rules |
| INIT-06 | Investigate standards | 3 and 4 | References and open questions recorded |
| INIT-07 | Draft acceptance criteria | 6 | Observable outcomes and degraded case |
| INIT-08 | Review readiness for design | All six | Scope, tools, responsibilities, next tasks reviewed |

## Keep the lifecycle visible

Use one dated note per meeting, short entries for significant decisions, and task records with owners and reviewers. Keep editable diagrams and their exports when design begins.

When online collaboration starts, a board can use **To do / In progress / Review / Done**. Use a small task per branch, descriptive commits, and another member's review before merging. Link tasks to documents or code. For now, keep the drafts local.

## Ready to leave preparation when

- [ ] Deadline and assignment constraints are recorded.
- [ ] All six agree responsibilities and can explain the scope.
- [ ] All six have verified the common environment, or have a documented alternative with an owner.
- [ ] One patient journey and the initial requirements are reviewed.
- [ ] Synthetic data, standards investigation, and security review have owners.
- [ ] Open questions and next design tasks are recorded.
