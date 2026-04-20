# AutoLineage User Study — Recruitment Posts

## Google Form Setup Instructions

Before posting any of these, create the Google Form. Here's the exact structure:

### Form Title
"AutoLineage User Study — 20 minutes, remote"

### Form Description
> I'm a researcher building AutoLineage, an automatic lineage tool for Python ML pipelines. I'm measuring how much faster automatic lineage makes data-quality debugging.
>
> **What's involved:** 20-minute screen-share session. I show you a small ML pipeline with a planted bug. You debug it using your normal workflow. Then I show you the same pipeline with AutoLineage, and we compare.
>
> **Compensation:** $25 Amazon gift card + acknowledgment in the paper.
> **Requirements:** Comfortable with Python, pandas, scikit-learn. 1+ years ML experience.
>
> Please fill this form if interested. I'll email you within 48 hours to schedule.

### Form Questions (copy these exactly)

1. **Name** (short answer, required)
2. **Email** (short answer, required, email validation on)
3. **LinkedIn or GitHub profile** (short answer, optional — helps verify experience)
4. **Years of Python/ML experience** (multiple choice)
   - Less than 1 year
   - 1-2 years
   - 3-5 years
   - 5+ years
5. **Current role** (short answer — e.g., "ML engineer at X", "PhD student in Y")
6. **Primary ML tools you use daily** (checkboxes)
   - pandas
   - scikit-learn
   - PyTorch
   - TensorFlow/Keras
   - PySpark
   - XGBoost/LightGBM
   - MLflow
   - Weights & Biases
   - Other
7. **How often do you debug data quality issues?** (multiple choice)
   - Multiple times per week
   - Weekly
   - Monthly
   - Rarely
8. **Time zones and availability** (paragraph) — "e.g., I'm in PST, available evenings and weekends"
9. **Any questions or comments?** (paragraph, optional)

### Settings
- Collect emails: ON (required for follow-up)
- Limit to 1 response per person: ON
- Don't require sign-in (cast wider net)

---

## IMPORTANT: Before Posting

**Get the form link.** It will look like `https://forms.gle/abc123XYZ`. Use that link in every post below (replace `FORM_LINK` placeholder).

**Set up calendar availability.** Use Cal.com (free) or Calendly. Create a 30-minute slot type called "AutoLineage Study" with buffer time. You'll send this to approved participants.

---

## Post 1: Reddit r/MachineLearning

**Title:** `[P] User study: help me measure debugging-time savings from automatic ML lineage (20 min, $25 gift card)`

**Body:**

Hi r/ML,

I built AutoLineage, an open-source tool that automatically tracks lineage across pandas + sklearn + PySpark with zero code changes. Paper is near-ready but I need a proper user study before submitting to arXiv.

**What I'm measuring:** How much faster you can find a data-quality bug with automatic lineage vs. manual debugging (print statements, df.shape checks).

**The session (20 minutes):**
1. I screen-share a Python pipeline that produces F1 = 0 due to a planted bug
2. You debug it your normal way — I time you
3. I show you the same pipeline with AutoLineage output and time myself
4. 4 quick questions at the end

**What you get:**
- $25 Amazon gift card
- Acknowledgment in the paper
- Early access to the tool if you want it

**Requirements:** Comfortable with Python, pandas, sklearn. 1+ years ML work experience.

**Sign up:** FORM_LINK

Happy to answer questions in the comments. Repo is at github.com/kishanraj41/autolineage if you want to poke around first.

---

## Post 2: LinkedIn Post

**Post:**

Running a short user study for a research paper on ML pipeline debugging.

If you work with Python + pandas/sklearn and can spare 20 minutes this week or next, I'd appreciate your help.

The session: I show you a buggy ML pipeline, you debug it. Then I show you the same pipeline with my tool (AutoLineage) and we compare. That's it.

$25 Amazon gift card + acknowledgment in the paper.

Sign up: FORM_LINK

(Paper is about automatic lineage tracking across pandas/sklearn/PySpark — no setup required, just one import. Would love your input.)

#MachineLearning #MLOps #Python #Research

---

## Post 3: Twitter/X Thread

**Tweet 1:**
Running a 20-minute user study for my ML research paper this week.

You debug a Python ML pipeline with a planted bug. I time you. Then I show you the same pipeline with my lineage tool.

$25 Amazon gift card + paper acknowledgment.

Sign up 👇

**Tweet 2:**
AutoLineage automatically tracks every pandas, sklearn, and PySpark operation across your pipeline with zero code changes.

One `import`. 288 hooks. 6.1% overhead.

But I need real data on whether it actually helps debugging. That's where you come in.

**Tweet 3:**
Requirements: comfortable with Python + ML, 1+ year experience.

Session: 20 min over Zoom/Meet. I screen-record for the paper.

Sign up: FORM_LINK

Happy to answer questions in replies.

---

## Post 4: ML/MLOps Discord servers

Paste in #jobs, #research, or #projects channels (whichever fits each server):

> Hi all — I'm doing a 20-min user study for an ML research paper. You debug a Python pipeline, I time you, we compare to my automatic lineage tool.
>
> $25 Amazon card + paper acknowledgment. Need 1+ year Python/ML experience.
>
> Sign up: FORM_LINK
>
> Happy to answer questions!

Servers worth posting in (check their rules first):
- MLOps.community Slack
- Papers We Love Discord
- Weights & Biases community
- Hugging Face Discord
- Python Discord

---

## Post 5: Direct outreach template

For messaging people you know who work in ML. Send via LinkedIn/email/Slack:

> Hey [Name],
>
> Hope you're well. I'm wrapping up a research paper on ML pipeline debugging and running a short user study — would you be willing to help?
>
> 20 minutes over Zoom. You debug a buggy Python pipeline, I time you. Then I show you my tool and we compare. That's it.
>
> $25 Amazon card + I'll credit you in the paper's acknowledgments.
>
> Let me know if you've got a window this week or next. Totally casual.
>
> Thanks!
> Kishan

---

## Tracking Responses

Create a spreadsheet with these columns:

| Name | Email | Source | Experience | Signed up date | Scheduled date | Completed? | Gift card sent? |
|------|-------|--------|-----------|----------------|----------------|------------|-----------------|

This matters for the paper — reviewers will ask "where did participants come from?" and you need to answer honestly.

---

## Expected Timeline

- **Day 1 (today):** Post on all channels
- **Day 2-3:** First responses come in. Screen for legitimate candidates (check LinkedIn/GitHub).
- **Day 3-7:** Run sessions as they schedule. Aim for 5-8 participants.
- **Day 8:** Compile results. Send me the data.
- **Day 9-10:** I write Section 5.4 with real N=5+ data.
- **Day 11:** Submit to arXiv.

## Target Participants

Minimum: 5 (paper calls it "pilot study")
Ideal: 10 (paper calls it "user study")
Stretch: 15 (paper can make statistical claims)

Don't run fewer than 5. N=3 is weaker than N=2 because it looks like you tried and couldn't recruit.

---

## Budget

At $25/participant × 8 participants = $200
Google Forms: free
Cal.com: free
Zoom: free tier works (40-min sessions fine)

**Total: $200.** Worth it for a real data point.

---

## Ethics Note

Before you run any session, read this consent statement to each participant:

> "I'm going to screen-record this session for research purposes. The recording will only be used by me and my co-author to analyze your debugging steps and won't be published or shared. Your name will appear in the paper's acknowledgments unless you prefer to stay anonymous. You can stop at any time. Do you consent?"

Wait for verbal "yes" before starting the recording.
