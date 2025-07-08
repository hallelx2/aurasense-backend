# Aurasense WebSocket Onboarding Integration Guide

This guide describes the standardized WebSocket protocol for real-time, voice-driven onboarding between the Aurasense frontend and backend. It covers:

- Onboarding progress updates
- Agent/user chat messages
- Audio message streaming (user to backend, backend to user)
- Message formats and recommended backend structure

---

## 1. WebSocket Connection

- **URL:** `${process.env.NEXT_PUBLIC_WEBSOCKET_URL}` (e.g., `wss://api.aurasense.com/ws`)
- **Protocol:** Socket.io (recommended for reliability, but can be adapted to raw WebSocket)
- **Auth:** Pass user/session token in connection params or as the first message after connect.

---

## 2. Message Types & Formats

### A. Onboarding Progress Update

**Backend → Frontend**

```json
{
  "type": "onboarding_progress",
  "payload": {
    "key": "dietaryPreferences", // one of the onboarding item keys
    "value": true                 // true if completed, false if reset
  }
}
```

- The frontend will update the checklist and, when all are true, redirect to the dashboard.
- Keys should match the agreed onboarding items:
  - `dietaryPreferences`
  - `restrictions`
  - `allergies`
  - `voiceSample`
  - `communityInterests`

### B. Agent/User Chat Message

**Backend → Frontend**

```json
{
  "type": "agent_message",
  "payload": {
    "id": "unique-message-id",
    "sender": "agent", // or "user"
    "text": "Please provide your dietary preferences.",
    "timestamp": "2024-05-01T12:34:56.789Z"
  }
}
```

- The frontend will display these in the chat area.
- The backend should echo user messages as needed for context.

### C. Audio Streaming (User → Backend)

**Frontend → Backend**

- When the user records and sends audio, emit:

```json
{
  "type": "user_audio",
  "payload": {
    "audioUrl": "https://s3.amazonaws.com/bucket/audio-file.webm", // or base64/blob if streaming
    "step": "dietaryPreferences", // which onboarding step this audio is for
    "timestamp": "2024-05-01T12:35:00.000Z"
  }
}
```

- The backend should process the audio, update onboarding progress, and respond with agent messages as needed.

### D. Audio Playback (Backend → Frontend)

**Backend → Frontend**

- To play back audio (e.g., agent TTS or confirmation), emit:

```json
{
  "type": "agent_audio",
  "payload": {
    "audioUrl": "https://s3.amazonaws.com/bucket/agent-response.webm",
    "text": "Thank you for providing your dietary preferences.",
    "step": "dietaryPreferences",
    "timestamp": "2024-05-01T12:35:05.000Z"
  }
}
```

- The frontend will play the audio and display the text in the chat.

---

## 3. Backend Structure & Streaming Recommendations

- **Session Management:**
  - Authenticate users on connect (token/session ID).
  - Track onboarding state per user.

- **Message Handling:**
  - Accept `user_audio` messages, process audio (ASR, intent, etc.), and respond with `agent_message` and/or `onboarding_progress`.
  - For each onboarding step, send `onboarding_progress` when the step is completed.
  - Optionally, send `agent_audio` for TTS or confirmation playback.

- **Streaming Audio:**
  - For real-time streaming, consider chunked audio (WebRTC, or base64 blobs in sequence), but for most onboarding flows, a single audio file per step is sufficient.
  - Use signed URLs for S3 or similar storage for audio files.

- **Frontend Playback:**
  - On receiving `agent_audio`, the frontend should play the audio and show the associated text in the chat.

---

## 4. Example Onboarding Flow

1. **User clicks microphone, records dietary preferences.**
2. **Frontend sends:**
   - `user_audio` with audio URL and step = `dietaryPreferences`
3. **Backend processes audio, updates state, and responds:**
   - `agent_message` ("Thank you for providing your dietary preferences.")
   - `onboarding_progress` (`key`: `dietaryPreferences`, `value`: true)
   - Optionally, `agent_audio` with TTS response
4. **Frontend updates checklist, plays audio, and moves to next step.**

---

## 5. Error Handling

- On error, backend can send:

```json
{
  "type": "error",
  "payload": {
    "message": "Could not process audio. Please try again."
  }
}
```

- The frontend should display this as a toast or chat message.

---

## 6. Extensibility

- Add more onboarding steps by extending the `ONBOARDING_ITEMS` list and using the same message structure.
- For multi-turn conversations, use the `agent_message` and `user_audio` types in sequence.

---

## 7. Security

- Always validate user/session tokens on connect and for each message.
- Use signed URLs for audio files.
- Never expose sensitive user data in chat or progress messages.

---

## 8. Contact

For questions or integration support, contact the Aurasense engineering team.
