# Promotional videos on the website

Public pages list and play promotional videos without a login. These are not course lessons. Do not call `/api/videos/{id}/otp` for them, and do not send an `Authorization` header.

Base URL: `https://africanhub-api.africanhub.ac.tz`

The API only returns videos an admin has published. Drafts are omitted from the list. Asking to play a draft, or any unknown slug, returns `404`.

## 1. List videos

`GET /api/promo-videos/public`

No query string and no body.

```json
{
  "status": "success",
  "data": [
    {
      "id": 3,
      "title": "How African Hub Works",
      "slug": "how-african-hub-works",
      "description": "Short introduction",
      "video_status": "ready",
      "thumbnail_url": "https://cdn.example/thumb.jpg",
      "cover_url": "https://africanhub-api.africanhub.ac.tz/storage/promo_videos/cover-abc.png",
      "video_duration": 95,
      "sort_order": 1
    }
  ]
}
```

The list is already ordered by `sort_order`, then `id`. Render it in that order.

| Field | Use |
|---|---|
| `slug` | The only id the website needs. Pass it to the play request. |
| `title` | Heading. |
| `description` | Optional text under the title. `null` when empty. |
| `cover_url` | Poster to show before play. Prefer this. |
| `thumbnail_url` | Fallback poster from VdoCipher when `cover_url` is `null`. |
| `video_duration` | Length in seconds. `0` when unknown. |
| `video_status` | `pending`, `processing`, `ready`, or `failed`. |

Show a play control only when `video_status` is `ready`. For `pending` or `processing`, show the cover and a short “not ready yet” label. Hide or disable play for `failed`.

An empty catalog is `{ "status": "success", "data": [] }`.

## 2. Play a video

Call this when the visitor presses play, not while rendering the list. Each response is a short-lived playback token. Request a new one for every play, including a replay after the player reports an error.

`POST /api/promo-videos/public/{slug}/play`

No body. Example: `POST /api/promo-videos/public/how-african-hub-works/play`

```json
{
  "status": "success",
  "data": {
    "otp": "<otp>",
    "playbackInfo": "<playbackInfo>",
    "video": {
      "id": 3,
      "title": "How African Hub Works",
      "slug": "how-african-hub-works",
      "description": "Short introduction",
      "video_status": "ready",
      "thumbnail_url": "https://cdn.example/thumb.jpg",
      "cover_url": "https://africanhub-api.africanhub.ac.tz/storage/promo_videos/cover-abc.png",
      "video_duration": 95,
      "sort_order": 1
    }
  }
}
```

Pass `otp` and `playbackInfo` to the VdoCipher web player. Do not store them, and do not put them in the page URL of the African Hub site.

### Player

Load the iframe only after the play request succeeds. `playbackInfo` must be URL-encoded.

```html
<iframe
  src="https://player.vdocipher.com/v2/?otp=OTP&playbackInfo=PLAYBACK_INFO"
  style="border:0;width:100%;aspect-ratio:16/9"
  allow="encrypted-media; fullscreen"
  allowfullscreen
></iframe>
```

```javascript
async function playPromo(slug, mount) {
  const response = await fetch(
    `https://africanhub-api.africanhub.ac.tz/api/promo-videos/public/${encodeURIComponent(slug)}/play`,
    { method: "POST" }
  );
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.message || "This video cannot be played right now.");
  }

  const params = new URLSearchParams({
    otp: body.data.otp,
    playbackInfo: body.data.playbackInfo,
  });
  mount.innerHTML = "";
  const frame = document.createElement("iframe");
  frame.src = `https://player.vdocipher.com/v2/?${params.toString()}`;
  frame.allow = "encrypted-media; fullscreen";
  frame.allowFullscreen = true;
  frame.style.border = "0";
  frame.style.width = "100%";
  frame.style.aspectRatio = "16 / 9";
  mount.appendChild(frame);
}
```

Replace the cover with this iframe inside the video’s own container. `URLSearchParams` encodes `playbackInfo`, so do not encode it a second time.

## Errors

Failures use `{ "status": "error", "message": "..." }`.

| HTTP | When | What to show |
|---|---|---|
| `404` | Slug is unknown, deleted, or still a draft | “Video not found.” |
| `425` | Published, but not playable yet. Body also includes `video_status`. | Keep the cover. “This video is not ready yet.” |
| `503` | Playback service is unavailable | “Playback is temporarily unavailable.” |
| `500` | Unexpected server error | “Something went wrong. Try again.” |

`425` example:

```json
{
  "status": "error",
  "message": "Video is not ready for playback.",
  "video_status": "pending"
}
```

## What the website should not do

- Do not require a logged-in user.
- Do not send the course-video OTP route a promotional slug or id.
- Do not cache `otp` or `playbackInfo` in local storage. Fetch them again each time someone presses play.
- The list never includes the VdoCipher video id. Play with `slug` only.
