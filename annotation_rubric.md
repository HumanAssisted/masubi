# Annotation Rubric -- Masubi

## 1. Overview

This rubric defines how to score email chains across 10 trust axes. Each chain is scored by 2-3 independent annotators. The resulting labels become ground truth for the gold set and judge calibration.

**General rules:**
- Score each axis independently; do not let one axis bias another.
- Score the entire chain, not individual emails -- later messages can change the meaning of earlier ones.
- Document uncertainty with a note field when unsure.
- Flag ambiguous chains for group discussion.

---

## 2. Binary Axes

Binary axes are scored as 0 (absent) or 1 (present).

### phish

**Definition:** The email chain contains a phishing attempt -- an effort to deceive the recipient into revealing credentials, financial information, or access through fraudulent pretense.

| Score | Criteria |
|-------|----------|
| **0** | Legitimate email. May contain links, requests, or urgency, but without deceptive intent. Includes marketing, transactional, internal business, personal correspondence. |
| **1** | Phishing attempt. Includes credential harvesting (fake login pages), financial fraud (fake invoices, wire transfer requests from impersonators), spear-phishing (targeted using personal details), and BEC (business email compromise). |

**Edge cases:**
- Legitimate password reset emails from real services: score 0.
- Emails that *look* like phishing but are legitimate (e.g., real IT department security alerts): score 0, add note.
- Incomplete phishing attempts (broken links, obvious errors): still score 1 -- intent matters.

### verify_by_search

**Definition:** The email chain contains claims that require external verification to assess truthfulness. The recipient would need to search the web or check external sources to confirm the claims.

| Score | Criteria |
|-------|----------|
| **0** | Self-contained. Claims are verifiable from the email context alone, are matters of opinion, or are trivially true (e.g., meeting time confirmations, personal greetings). |
| **1** | Requires search. Contains factual claims about events, statistics, policies, product specifications, regulatory changes, or other verifiable assertions that the recipient cannot confirm from the email alone. |

**Edge cases:**
- Internal company announcements about policy changes: score 1 if the recipient would reasonably want to verify.
- Widely known facts ("the sky is blue"): score 0.
- Claims about the sender's own feelings or intentions: score 0.

---

## 3. Continuous Axes

Continuous axes are scored from 0.0 (absent/benign) to 1.0 (maximum concern). Use the anchor points as calibration guides.

### truthfulness

**Definition:** Degree to which the email chain contains false, misleading, or unverifiable factual claims.

| Score | Description |
|-------|-------------|
| **0.0** | Fully truthful. All claims are accurate or clearly marked as opinion/speculation. |
| **0.5** | Mixed. Contains some inaccurate or misleading claims alongside truthful content. Exaggerations that could mislead but are not outright false. |
| **1.0** | Pervasively false. Core claims are fabricated, statistics are invented, identities are falsified. |

**Boundary:** Distinguish between honest mistakes (lower score) and deliberate fabrication (higher score). Score based on the content, not intent -- you cannot always determine intent.

### manipulation

**Definition:** Degree to which the email chain uses psychological tactics to influence the recipient's behavior beyond rational persuasion.

| Score | Description |
|-------|-------------|
| **0.0** | No manipulation. Straightforward communication, rational persuasion, honest requests. |
| **0.5** | Moderate manipulation. Uses artificial urgency ("act now!"), mild guilt-tripping, emotional appeals that go beyond stating facts, social proof pressure. |
| **1.0** | Heavy manipulation. Combines multiple tactics: manufactured crisis, isolation ("don't tell anyone"), gaslighting, threats disguised as concern, exploitation of trust relationships. |

**Boundary:** Legitimate urgency (actual deadline) vs. manufactured urgency (fake countdown). Enthusiasm vs. pressure. Score the *tactics*, not the topic.

### deceit

**Definition:** Degree to which the email chain contains hidden intent, misdirection, or deliberate concealment of relevant information.

| Score | Description |
|-------|-------------|
| **0.0** | Transparent. The sender's purpose is clear and honest. No hidden agendas. |
| **0.5** | Partial concealment. Key information is omitted or buried. The email is technically truthful but misleading by omission. The true purpose is obscured but discoverable. |
| **1.0** | Active deception. The stated purpose is a cover for the real intent. Information is deliberately falsified or hidden. The recipient is being set up. |

**Boundary:** Privacy (not sharing everything) vs. deceit (deliberately hiding relevant information). Business confidentiality (legitimate) vs. concealment to exploit (illegitimate).

### vulnerability_risk

**Definition:** Degree to which the email chain targets or exploits the recipient's vulnerable situation (financial distress, emotional state, age, technical inexperience, authority relationship).

| Score | Description |
|-------|-------------|
| **0.0** | No exploitation. Communication treats the recipient as a competent equal. |
| **0.5** | Moderate risk. Takes advantage of an information asymmetry or mild power dynamic. Offers that seem targeted at people in difficult situations. |
| **1.0** | Active exploitation. Specifically targets vulnerable populations (elderly, financially distressed, grieving). Uses knowledge of the recipient's situation against them. |

**Boundary:** Offering help to someone in need (0.0) vs. exploiting their need for profit (higher). Consider the power dynamic and whether the sender benefits at the recipient's expense.

### subtle_toxicity

**Definition:** Degree to which the email chain contains implicit toxicity, microaggressions, coded language, or othering that would not be caught by standard toxicity filters.

| Score | Description |
|-------|-------------|
| **0.0** | No toxicity. Respectful, inclusive communication. |
| **0.5** | Subtle signals. Backhanded compliments, stereotyping, dismissive tone toward a group, "jokes" that punch down, passive-aggressive phrasing. |
| **1.0** | Pervasive subtle toxicity. Systematic othering, coded discriminatory language, gaslighting about the recipient's concerns, creating a hostile environment through "plausible deniability" tactics. |

**Boundary:** Cultural directness (some cultures are more blunt) vs. rudeness. Constructive criticism vs. undermining. Consider the overall pattern, not isolated phrases.

### polarization

**Definition:** Degree to which the email chain uses zero-sum framing, us-vs-them rhetoric, emotional blackmail, or extreme positions to push the recipient toward a polarized view.

| Score | Description |
|-------|-------------|
| **0.0** | Balanced. Acknowledges nuance, presents multiple perspectives, or focuses on shared interests. |
| **0.5** | Moderate polarization. Frames issues as black-and-white, uses emotional language to characterize "the other side," implies loyalty tests. |
| **1.0** | Extreme polarization. Demonizes outgroups, demands total allegiance, uses catastrophizing ("if you don't act, everything is lost"), creates false dilemmas. |

**Boundary:** Strong opinions (acceptable) vs. framing that eliminates middle ground (polarizing). Advocacy (stating a position) vs. radicalization (demanding conformity).

### classic_email_metrics

**Definition:** Degree to which the email chain exhibits traditional spam/malicious email signals: poor formatting, suspicious headers, generic greetings, URL obfuscation, attachment lures, etc.

| Score | Description |
|-------|-------------|
| **0.0** | Professional/personal quality. Well-formatted, appropriate salutations, clean URLs, no suspicious patterns. |
| **0.5** | Some red flags. Generic greeting ("Dear Customer"), minor formatting issues, somewhat suspicious links, slight brand mismatches. |
| **1.0** | Classic spam/malicious signals. ALL-CAPS, excessive punctuation, URL shorteners/obfuscation, fake headers, attachment lures ("see attached invoice"), lottery/prize notifications. |

**Boundary:** Informal writing style (acceptable) vs. spam signals (suspicious). Marketing emails may score 0.2-0.4 even if legitimate.

### authority_impersonation

**Definition:** Degree to which the email chain falsely claims or implies authority, rank, title, or organizational affiliation to influence the recipient.

| Score | Description |
|-------|-------------|
| **0.0** | No impersonation. The sender's authority claims are legitimate or absent. |
| **0.5** | Implied authority. Uses vague titles, drops names without direct affiliation, implies organizational backing without stating it. Legitimate authority used in slightly overreaching ways. |
| **1.0** | Full impersonation. Claims to be a specific person (CEO, IT admin, government official) they are not. Uses fake letterheads, forged signatures, spoofed sender addresses. |

**Boundary:** Friendly authority ("as your manager, I suggest...") when the person IS the manager = 0.0. Same claim when they are NOT the manager = 0.8-1.0. The key question: is the authority claim truthful?

---

## 4. Edge Cases

### Multi-intent emails
Score each axis independently based on the content relevant to that axis. An email can be simultaneously a legitimate business request (phish=0) that uses manipulative urgency (manipulation=0.6).

### Sarcasm and humor
Score both the surface intent AND the likely interpretation. If sarcasm could be misread as genuine, score based on how a reasonable recipient would interpret it. Add a note explaining the sarcasm.

### Cultural context
Some communication styles vary by culture (directness, formality, authority deference). When cultural norms affect interpretation, score based on the likely impact on the intended audience, not your own cultural baseline. Add a note about cultural considerations.

### Thread context
Later emails in a chain can change the meaning of earlier ones. Score the chain as a whole. An initial legitimate email followed by a fraudulent follow-up makes the chain higher-risk even if email #1 alone was benign.

### Forwarded/quoted content
Score the sender's intent and additions, not merely the quoted material. If someone forwards a phishing email with "FYI, this is a scam," the chain scores low on phish.

---

## 5. Annotator Instructions

### Process
1. **Calibration phase (first 20 chains):** All annotators score the same chains, then discuss disagreements to align on rubric interpretation. Resolve ambiguities and add notes to this rubric.
2. **Independent scoring:** After calibration, score independently. Do not discuss individual chains with other annotators.
3. **Flagging:** Mark any chain as "ambiguous" if you are uncertain about any axis. These will be reviewed jointly.

### Per-chain workflow
1. Read the entire email chain before scoring any axis.
2. Score each axis in order (phish first, authority_impersonation last).
3. For binary axes: record 0 or 1.
4. For continuous axes: record a float from 0.0 to 1.0 in increments of 0.1.
5. Add a brief note for any score where you feel uncertainty > 20%.
6. If the chain is ambiguous overall, flag it.

### Quality checks
- If your scores for a chain are all 0.0 or all 1.0, double-check -- most real emails have mixed signals.
- If you disagree with another annotator by > 0.3 on a continuous axis, this will be flagged for review during calibration.
- Periodically re-score a chain from the calibration set to check your own consistency.
