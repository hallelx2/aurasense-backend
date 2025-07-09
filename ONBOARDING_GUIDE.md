
# Frontend Onboarding Integration Guide (REST API)

This guide explains how to integrate the user onboarding process with your frontend application using the available RESTful API endpoints.

## Onboarding Fields

The primary goal of the onboarding process is to gather the following information from the user to personalize their experience. Your frontend should be prepared to prompt the user for this information.

- `age`: The user's age (integer).
- `dietary_restrictions`: A list of dietary restrictions (e.g., `["vegetarian", "gluten-free"]`).
- `cuisine_preferences`: A list of preferred cuisines (e.g., `["italian", "mexican"]`).
- `price_range`: The user's preferred price range for dining (`"budget"`, `"mid-range"`, `"premium"`, or `"luxury"`).
- `is_tourist`: A boolean indicating if the user is a tourist.
- `cultural_background`: A list of the user's cultural backgrounds (e.g., `["nigerian", "american"]`).
- `food_allergies`: A list of food allergies (e.g., `["nuts", "shellfish"]`).
- `spice_tolerance`: The user's spice tolerance on a scale from 1 to 5 (integer).
- `preferred_languages`: A list of preferred languages (e.g., `["en", "es"]`).

## API Flow

The onboarding process is managed through a series of API calls. The user must be authenticated, and a valid JWT Bearer token must be included in the `Authorization` header for all requests.

### Step 1: Start the Onboarding Process

To begin the onboarding flow, make a POST request to the `/onboarding/start` endpoint. This will create a new onboarding session.

**Endpoint:** `POST /onboarding/start`

**Request Body:** An empty JSON object.

```json
{}
```

**Response:**

The response will contain a unique `session_id` for this onboarding session, the first question to ask the user (`message`), an audio version of the message, the current `onboarding_status`, and the user's `progress`.

```json
{
    "session_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "message": "Do you have any dietary restrictions? For example, vegetarian, vegan, gluten-free, etc.",
    "audio_response": "...", // base64 encoded audio data
    "onboarding_status": "pending_info",
    "progress": 10.0,
    "user_id": "user_uid_here",
    "success": true
}
```

### Step 2: Process User Input

For each piece of information the user provides, send it to the `/onboarding/input` endpoint. The user's response should be in plain text.

**Endpoint:** `POST /onboarding/input`

**Request Body:**

- `transcript`: The user's text response.
- `session_id`: The `session_id` received from the `/start` endpoint.

```json
{
    "transcript": "I am a vegetarian.",
    "session_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef"
}
```

**Response:**

The response will contain the next question to ask the user, along with the updated status and progress. Continue this process until the `onboarding_status` is `"onboarded"`.

```json
{
    "session_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "message": "What are your favorite types of cuisine? Tell me about the foods you love!",
    "audio_response": "...", // base64 encoded audio data
    "onboarding_status": "pending_info",
    "progress": 25.0,
    "extracted_info": {
        "dietary_restrictions": ["vegetarian"]
    },
    "user_id": "user_uid_here",
    "success": true
}
```

### Step 3: Handle Onboarding Completion

When the agent has gathered all the necessary information, the `onboarding_status` in the response from `/onboarding/input` will be `"onboarded"`.

**Response when complete:**

```json
{
    "session_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "message": "Congratulations! Your personalization is complete. Welcome to your personalized Aurasense experience!",
    "audio_response": "...", // base64 encoded audio data
    "onboarding_status": "onboarded",
    "progress": 100.0,
    "extracted_info": {
        "dietary_restrictions": ["vegetarian"],
        "cuisine_preferences": ["italian"],
        // ... all other fields
    },
    "user_id": "user_uid_here",
    "success": true
}
```

At this point, the user's profile has been updated in the database, and you can redirect them to the main part of your application.

### Step 4: (Optional) Stop the Onboarding Process

If the user wishes to stop the onboarding process before it's complete, you can call the `/onboarding/stop` endpoint.

**Endpoint:** `POST /onboarding/stop`

**Request Body:**

```json
{
    "session_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef"
}
```

**Response:**

```json
{
    "session_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "message": "Great! Let's start exploring delicious food options for you.",
    "redirect_to": "/food-selection",
    "user_id": "user_uid_here",
    "success": true
}
```

This will clean up the session data and provide a redirect suggestion.
