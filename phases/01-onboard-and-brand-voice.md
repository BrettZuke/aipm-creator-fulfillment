# Phase 1. Onboard, scrape their socials, write the brand voice

**Deliverable:** a signed-off brand voice document, an offer you both agree on, and
every asset and login you need to work without asking them again.

**Done when:** you can write a piece of content in their voice and they read it and say
"that sounds like me".

---

## 1. Send the onboarding form

Do not send instructions. Send one link.

Clone [ai-partner-method-onboarding](https://github.com/BrettZuke/ai-partner-method-onboarding).
It has the creator intake form and the follow-up sequence. Host the form with
[settoku-forms](https://github.com/BrettZuke/settoku-forms) so you own the responses,
or use the ready-made templates in
[aipm-student-form-templates](https://github.com/BrettZuke/aipm-student-form-templates).

The form must capture, at minimum:

- Every social handle, and the analytics logins for each
- Their current offer, price, and what the buyer actually gets
- Their email platform and list size
- Existing funnel URLs, VSLs, lead magnets
- Who their buyer is, in their words
- The three questions they get asked most

Send it the moment they pay. Not before.

## 2. Scrape everything they have already published

Their own back catalogue is the voice training data. Run all of it.

```bash
# Profile + recent posts -> .tmp/<username>/profile.json, posts.json
python3 tools/instagram/scrape_creator_dossier.py --username theirhandle --posts 50

# Deep historical pull across IG and TikTok, rotates Apify tokens to beat the per-token cap
python3 tools/instagram/scrape_creator_deep.py --username theirhandle --ig-posts 200 --tt-posts 80

# YouTube videos + transcripts, free, no API quota
python3 tools/youtube/scrape_youtube_creator.py --channel @theirchannel --max-videos 50 --transcripts 15
```

Then transcribe the reels. The transcripts are what carry the voice, not the captions.

```bash
python3 tools/instagram/transcribe_reels_from_apify.py
```

If YouTube blocks the free transcript path, fall back to
`python3 tools/youtube/apify_yt_transcripts.py`.

## 3. Write the brand voice

Use the `client-brand` skill from
[aipm-skill-pack](https://github.com/BrettZuke/aipm-skill-pack), fed with the reel
transcripts from step 2. Transcripts over captions, always: captions are written, reels
are spoken, and you are trying to capture how they actually talk.

Cross-check the output against `sops/personal_brand_sop.md`.

Then run the voice document past `skills/avoid-ai-writing` and `skills/stop-slop` before
you send it. If it reads like AI wrote it, they will not trust anything you send after it.

## 4. Lock the offer

`sops/offer_creation_sop.md` is the process. Do not skip this because they "already have
an offer". Most creators have a price and a name, not an offer.

You need, written down and agreed:

- Who it is for, specifically enough to exclude people
- The one outcome
- Why it works when the things they already tried did not
- The price, and what happens on the call

Phase 5's VSL is written off this document. If it is vague here, the VSL is vague.

---

## Checklist

- [ ] Onboarding form sent as a single link, immediately after payment
- [ ] All socials scraped, reels transcribed
- [ ] Brand voice document written from transcripts, run through the anti-slop skills
- [ ] Client has read the voice document and confirmed it sounds like them
- [ ] Offer document written and agreed
- [ ] Every login captured, in your password manager, not in a chat thread
