# Scams on Record: channel gameplan

One true scam case a day, faceless, about 65 to 75 seconds, built only from official records. Every story is real and the source is on screen. The working copy of this plan also lives in Claude Docs as "Faceless Scam Story Channel Gameplan".

## Series
Numbered series so viewers binge the back catalog.

| Series | What each episode is | Where the story comes from |
| --- | --- | --- |
| Caught #N | One real case followed from first contact to the sentencing | DOJ and U.S. Attorney press releases (justice.gov/news) |
| Scam Alert #N | A new official warning, told as "here's how it plays out" | FTC Consumer Alerts, FBI IC3 announcements |
| Red Flag Friday #N | One scam message on screen with every warning sign circled | FTC sample messages, the owner's own spam folder |

Caught carries the drama because every case has a real ending. Scam Alert keeps the channel current. Red Flag Friday is the light one for busy weeks.

## The look
Rendered in code (`tools/video/engine.py` plus each episode's `video/render.py`). Dark animated gradient background with grain and drifting particles, frosted glass cards, story-style progress bar, word-synced captions with the active word in yellow, zoom-blur cuts with a light sweep.

Building blocks used so far (Caught #1):
- Gavel strike and a rolling odometer number for the hook
- Phone mock-up (incoming call, then a call transcript) under a REENACTMENT label
- Paper quote card "FROM THE U.S. ATTORNEY'S RELEASE" with a yellow marker sweep on the key words
- Cash flying into a box, the box shipped along a dashed path to a pulsing pin
- Case file dossier with typed fields and a faceless silhouette
- Dot-matrix map with pins, glowing routes and incoming report arcs
- SENTENCED stamp slam with screen shake and a red flash, then counting stat rows
- RED FLAGS rows with animated X icons, a green "Hang up" action card, the follow pill and the source line

## Beat sheet (every episode)
| Beat | Time | Voiceover | Screen |
| --- | --- | --- | --- |
| 1. Hook | 0 to 8 s | The strongest true fact, stated plainly | The number or the outcome, big |
| 2. Setup | 8 to 15 s | How first contact happened | Phone, message or ad |
| 3. Trust | 15 to 24 s | How the scammer made it feel real | Reenactment plus a quote card |
| 4. The ask | 24 to 30 s | The money request | Cash, transfer, gift cards, crypto |
| 5. The fall | 30 to 44 s | Who did what, and how it came apart | Dossier, map, timeline |
| 6. Ending | 44 to 54 s | Plea, verdict or warning | Stamp and stats |
| 7. Red flags | 54 to 67 s | The warning signs and what to do instead, then "Follow for [series] #N+1" | Checklist, action card, source line |

## Drama without inventing
- Present tense ("It starts with a phone call").
- Hold the number: a beat of silence, then the figure with a sound hit.
- Something new on screen every 2 to 3 seconds.
- Quote the record on screen. It hits harder than a paraphrase and proves the story is real.
- Split a long case into Part 1 and Part 2, ending Part 1 when the money leaves.
- Every accuracy rule in RULES.md still applies.

## Weekly routine (7 episodes, about 6 hours)
| Day | Task |
| --- | --- |
| Sunday | Pick 7 sources (4 Caught, 2 Scam Alert, 1 Red Flag Friday). Write the scripts with the prompt below. Independent fact-check. |
| Monday | Generate voice (`tools/voice/gen_vo.py`), align (`tools/voice/align.py`), build each episode's `video/render.py` from the last one. |
| Tuesday | Render, mix, watch every video once on a phone. |
| Wednesday | Schedule the week on TikTok, YouTube, Instagram and Facebook. |
| Daily | 10 minutes of comment replies. Questions like "is this text real?" become Red Flag Friday episodes. |

Where to find sources: [justice.gov/news](https://www.justice.gov/news) (search "fraud" or "scheme"), [consumer.ftc.gov/consumer-alerts](https://consumer.ftc.gov/consumer-alerts), [ic3.gov](https://www.ic3.gov) public service announcements.

## Script prompt
Paste into Claude with the full source text under it.

```
You are writing a 65 to 75 second faceless TikTok script for Scams on Record, series [Caught / Scam Alert / Red Flag Friday], episode #[N].
Read RULES.md and persona/NARRATOR.md in the scamsonrecord-ops repo first and follow them.
Use ONLY facts stated in the source text below. Do not add names, numbers, dates, places, feelings or events that are not in it.
If a beat needs a detail the source does not give, write [NOT IN SOURCE] there instead of guessing.
If the person is only charged or indicted, say "accused" and "prosecutors say".
Refer to victims only the way the source does. Describe the defendant by role, age (with whose age and when) and city.
Write in present tense, short sentences, plain words, 170 to 190 spoken words, numbers spelled the way they are said.
Follow the seven beats in GAMEPLAN.md and open with the strongest true fact stated plainly.
For each beat give VOICEOVER, ON SCREEN, and the exact source sentence that backs it.
End the voiceover with: "Follow for [series] number [next]."
After the script list: the red flags shown on screen, a short title, a caption with the source URL, and 5 hashtags.
Source URL: [paste URL]
Source text:
[paste the full text]
```

## First 30 days
- Week 1: claim the handle on all four platforms, post Caught #1, build the next six from the same engine.
- Week 2: one a day across all three series. Try two hook styles.
- Week 3: Black Friday and Cyber Monday week. Tilt Scam Alert toward fake online stores and delivery texts.
- Week 4: one to two a day, cross-posted everywhere.
- Day 30: keep the series with the best average watch time, rework or drop the weakest.

Numbers to check every Sunday in TikTok Studio: average watch time and finish rate, where the retention graph drops (a cliff in the first 3 seconds means the hook failed), shares and saves, follows per video.

## Money path
| Stream | When it opens | What it pays |
| --- | --- | --- |
| Affiliate links (identity theft protection, password managers) | Day 1, link in bio and caption, always disclosed | A commission per signup |
| Sponsors (security and privacy brands) | Once views are steady | A flat fee per video. Sponsored videos don't earn Creator Rewards ([source](https://blog.brandbastion.com/tiktok-creator-fund-vs-creator-rewards)) |
| TikTok Creator Rewards | 10,000 followers, 100,000 views in 30 days, Personal account, 18+, videos over 1 minute ([source](https://ttcalculator.net/learn/creator-rewards-program/)) | About $0.40 to $1.00 per 1,000 qualified views ([source](https://www.argil.ai/blog/does-tiktok-pay-for-views)) |
| YouTube Partner Program | 1,000 subscribers plus 4,000 watch hours in 12 months or 10 million Shorts views in 90 days. New applicants need double from Feb 1, 2027 ([source](https://air.io/en/monetization/youtube-partner-program-requirements-2026-the-complete-guide)) | Share of ad revenue |

Keep the TikTok account Personal. Business accounts can't join Creator Rewards, and switching back means a 30-day wait ([source](https://virlo.ai/blog/is-tiktok-creator-reward-program-really-worth)).
