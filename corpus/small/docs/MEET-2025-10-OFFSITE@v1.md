**Document ID:** MEET-2025-10-OFFSITE
**Version:** v1
**Title:** Architecture offsite notes
**Date:** 2025-10-09
**Status:** Informal

---

# Architecture offsite notes

Rough notes, typed up the evening after. Not minutes, not a decision log. **Nothing here was decided.** If you need to know what we are actually doing about something, look for the ADR or RFC, not these notes. Corrections welcome, just edit or ping whoever is nearest.

## The venue

Honestly the venue deserves its own section because it set the tone for the whole day.

- Big room with proper windows, which after months of windowless meeting rooms felt almost suspicious. Several people commented that they had forgotten what daylight did to their ability to think.
- The whiteboards were huge but the markers were, as tradition demands, about half dead. Someone did a heroic run to find working ones before the first session. We should just bring our own next time.
- Wifi was patchy in the back corner. The people who sat there claimed it was a feature because they actually listened instead of reading messages.
- Lunch was good. The coffee was not. The afternoon slump was real and we lost about one session's worth of energy after lunch.
- The breakout spaces were great for small groups. People wandered outside during the long break and a few of the better conversations of the day happened on the walk.

General feeling: good place, would go again, bring markers and a decent coffee plan.

## Morning: roadmap brainstorming

We started with an open "what is bugging you about Orion" round. Everyone got sticky notes and a few minutes. This was messy and fun and produced far more notes than we could discuss, so we clustered them on the big wall.

Clusters that came up (in no particular order, and with no ranking or commitment attached):

**Observability.** Lots of notes along the lines of "I cannot tell what is going on across services". People want better tracing across service boundaries and dashboards that are designed for incidents rather than for status meetings. A few people pointed at recent incidents where we lost time just figuring out which errors mattered.

**Retry and resilience patterns.** Several notes about every service doing retries its own way. Some appetite for shared libraries or guidelines, some worry that a shared library becomes a bottleneck nobody wants to own. Good discussion, no conclusion.

**API consistency.** The usual grumbles about naming, error formats and pagination being slightly different everywhere. Someone said the API versioning story is "fine until you look at it closely". People generally want a style guide that is actually enforced, but there was disagreement about whether enforcement should be tooling or review.

**Event driven everything?** A lively argument about how far to lean into events versus direct calls. One camp wants more things to happen asynchronously. The other camp points out that debugging asynchronous flows is hard and we are not great at it yet. This went round in circles for a while. Parked.

**Developer experience.** Local environments are painful. Spinning up enough of Orion to test a change is slow and flaky. This got the most sticky notes of any cluster, which probably says something.

**Documentation.** A meta moment: several notes saying our docs are hard to find and sometimes contradict each other. People want superseded docs marked clearly. (Yes, we noticed the irony of writing that on sticky notes.)

We did a dot voting exercise at the end of the morning, but it was explicitly a "what do people care about" pulse, not a prioritisation. The facilitator was clear on this and we should be too. Do not quote the dot vote as a roadmap.

## Afternoon: blue sky session

The afternoon was "if we were starting Orion from scratch, what would we do differently". Some highlights, all speculative:

- A few people said they would put far more effort into contracts between services up front.
- Someone argued passionately that we should have a single front door for all clients. Others pointed out this has been proposed before and reminded the room why it stalled. Fair points on both sides.
- There was a thoughtful thread about whether some services are too small and should be merged, versus others that are doing far too much.
- Data ownership came up repeatedly. Who owns which data, and what other services are allowed to do with it, is not always obvious.

The session was useful mainly for surfacing assumptions, not for producing answers. Several people said afterwards it was the part of the day they enjoyed most.

## Team morale

We set aside time for an honest check in on how people are feeling. Paraphrased and anonymised:

- People are tired. The last stretch has had a lot of incident load and migration work running in parallel, and that adds up.
- On call is the biggest source of stress. Not the volume of pages so much as the feeling of being paged for things you cannot fix.
- Several people said they feel good about the quality of collaboration across teams, especially during incidents. The blameless postmortem culture came up as something people value.
- Some frustration about context switching. People want longer stretches of focused time.
- Newer folks said the platform is intimidating and the offsite helped them see the bigger picture. More of this kind of session was requested.
- A couple of people said it was just nice to be in a room together and talk without an agenda.

Nobody tried to fix morale in the room, which was probably the right call. It was mostly about listening. Managers said they would think about what they heard.

## Odds and ends

- Someone brought homemade snacks for the afternoon and saved the day after the coffee situation.
- Quiz at the end. The question about the history of our old message broker caused an unreasonable amount of debate.
- Group photo exists somewhere, ask around.

## Possible follow ups (not decisions)

These are ideas people floated as things someone might want to look into. None are assigned and none are agreed:

- Someone could write up the observability pain points properly.
- Maybe an RFC on shared retry guidance, if anyone has energy for it.
- Maybe a short session on local development pain.
- Run another one of these, possibly with better coffee.

Thanks to everyone who came, and to whoever organised the venue.
