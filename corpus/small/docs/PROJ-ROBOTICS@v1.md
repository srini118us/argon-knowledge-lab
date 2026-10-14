# Warehouse robotics pilot

| | |
|---|---|
| Document ID | PROJ-ROBOTICS |
| Version | v1 |
| Title | Warehouse robotics pilot |
| Date | 2025-05-12 |
| Status | Pilot |

## TL;DR

Northwind Logistics is piloting autonomous mobile robots for picking support in one warehouse. **The pilot runs in the Columbus warehouse.** It is an operations experiment first and a technology project second. **The pilot is unrelated to Orion and has no integration with it yet.** If you work on the Orion order management platform, nothing in this brief requires action from you.

## Why we are doing this

Warehouse teams have told us the same thing for a while: a lot of a picker's shift is spent walking, not picking. Long walks between pick faces, back and forth to packing stations, doubling back for a missed item. Walking is tiring, it is the part of the job people like least, and it is the part that scales worst when volumes spike.

Robotics vendors claim that mobile robots which carry totes between pickers and packing stations can take much of that walking off people's feet. We would like to find out whether that holds up in a Northwind building, with Northwind layouts, Northwind product mix and Northwind people, before anyone talks about rolling it out further.

## What the pilot is

- A small fleet of mobile robots working a defined zone of the Columbus warehouse.
- Pickers stay in their zones and place items into totes carried by the robots. The robots move totes to packing.
- The robots run on their own fleet management software, supplied as part of the pilot, with its own tablet interface for supervisors.
- Work for the robots is set up by the site team using the fleet software directly.

## What the pilot is not

- **Not an Orion project.** The robots do not receive orders from Orion, do not report back to Orion, and do not read from or write to any Orion service. Any order information the site team needs is handled with their existing tools and processes.
- Not a commitment to a vendor, or to robotics at other sites.
- Not a headcount exercise. The question is whether robots make the work better and smoother, not whether they replace people.

## Questions we want answered

1. **Does it actually reduce walking?** We will compare how pickers in the robot zone spend their time with comparable pickers working the traditional way.
2. **Do people like working with it?** Picker and supervisor feedback carries as much weight as the throughput numbers. A tool people resent will not survive peak season.
3. **How does it behave on a bad day?** Blocked aisles, dead batteries, a robot that stops in the wrong place, network drop outs. We care more about graceful failure than about best case speed.
4. **What does it take to run?** Who charges the robots, who clears faults, who updates maps when racking moves, and how much of the site team's time does that consume?
5. **What would integration need?** Not to build it, but to understand what a future connection to order systems might require, so that any later decision starts from facts.

## Phases

**Phase 1: Set up.** Map the zone, install charging points, configure the fleet software, train the first group of pickers and supervisors. Robots run in a supervised mode while everyone learns.

**Phase 2: Normal operations.** Robots support regular shifts in the zone. The site team runs them with vendor support on hand. We collect observations and feedback throughout.

**Phase 3: Review.** Operations, the site team and the vendor review what was learned. Output is a recommendation: stop, extend the pilot, or propose a wider trial.

## Roles

- **Pilot sponsor:** a senior operations leader, accountable for the go / no go recommendation.
- **Site lead:** the Columbus warehouse manager, accountable for day to day running and for the people in the pilot zone.
- **Pilot coordinator:** runs the plan, gathers feedback, keeps the vendor relationship moving.
- **Safety representative:** signs off the zone layout and procedures before robots run alongside people, and has the authority to pause the pilot at any time.
- **Technology liaison:** a single named contact on the technology side who answers questions about networks, devices and security for the pilot hardware. This is an advisory role. No engineering team is assigned to the pilot.

## Safety

Robots and people share aisles. Before Phase 2 starts:

- Every person working in or passing through the zone completes the site induction for the pilot.
- Zone boundaries are clearly marked on the floor.
- Emergency stop procedures are posted and practised.
- The safety representative walks the zone and signs off.

Any safety concern, however minor, is reported to the site lead on the same shift. When in doubt, stop the robots.

## Data and security

The robots and their fleet software run on a segregated network at the site. They do not connect to Northwind's order systems. Data collected during the pilot (robot movement logs, task timings, feedback surveys) stays with the pilot team and is used only for the review.

## Relationship to Orion, stated plainly

People keep asking, so to be explicit: **there is no integration with Orion today.** If the pilot succeeds and a wider rollout is proposed, connecting robots to order data would be a separate piece of work with its own design review, its own owners and its own decision record. Nothing in this pilot assumes that work will happen, and no Orion team should plan for it on the basis of this brief.

## Open questions

- How should we capture the "bad day" scenarios fairly, given that the zone will be watched more closely than a normal area?
- What is the right comparison group inside the same building?
- How do we keep the pilot zone representative when the site team is, understandably, excited about it?

## Feedback

Comments on this brief go to the pilot coordinator. Floor level feedback goes to the site lead.
