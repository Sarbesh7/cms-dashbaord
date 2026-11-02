# CSITABMC Mobile Push Notification Device API

This document is the standalone integration reference for mobile application developers integrating device push notification tokens with the CSITABMC backend.

---

## 1. Overview & Base Configuration

The backend provides two public endpoints for managing device push notification tokens:
1. **Register / Re-enable Push Token**: Call upon app startup / permission grant to register an Expo Push Token.
2. **Unregister / Disable Push Token**: Call when the user turns push notifications off (opt-out).

### Environment Configuration

The mobile app's environment configuration specifies the API base:

```env
EXPO_PUBLIC_STRAPI_API_URL=https://dashboard.csitabmc.com/api
```

Since the API base already includes `/api`, endpoints relative to this base are:
- `/push-devices/register`
- `/push-devices/unregister`

### HTTP Headers & Authentication Policy
- **No Authorization header or JWT is required**: Both endpoints are public.
- **Request Headers**:
  - `Content-Type: application/json`
  - `Accept: application/json`
- **Response Format**: The backend **always returns valid JSON** with status `200 OK` or `201 Created`. The backend will **never** return `204 No Content` or an empty body.
- **Timeout**: The mobile client enforces a **10-second timeout**. All responses finish well within <100ms.

---

## 2. Endpoints Reference

### 2.1 Register or Re-enable Device Token

Registers a new Expo push token or re-enables a previously disabled token.

- **URL**: `/api/push-devices/register`
- **Full URL**: `https://dashboard.csitabmc.com/api/push-devices/register`
- **Method**: `POST`
- **Auth**: None (Public)

#### Request Body (JSON)

| Field | Type | Required | Description |
|---|---|---|---|
| `token` | `string` | **Yes** | Expo Push Token. Must start with `ExponentPushToken[` or `ExpoPushToken[`. |
| `platform` | `string` | **Yes** | Operating system platform. Must be `'android'` or `'ios'` (case-insensitive). |

```json
{
  "token": "ExponentPushToken[example-device-token]",
  "platform": "android"
}
```

#### Successful Responses

**Case A: New Device Registered**
- **HTTP Status**: `201 Created`
- **Response Body**:
```json
{
  "success": true,
  "registered": true,
  "message": "Device registered successfully"
}
```

**Case B: Existing Token Re-enabled or Already Active**
- **HTTP Status**: `200 OK`
- **Response Body**:
```json
{
  "success": true,
  "registered": false,
  "message": "Device already registered"
}
```

#### Error Responses

- **HTTP Status**: `400 Bad Request`
```json
{
  "error": "Push token is required",
  "details": {
    "token": ["Push token is required"]
  }
}
```
*(Or `"Invalid Expo push token"` if the string does not match the Expo token prefix, or `"Platform must be android or ios"` if the platform is not supported.)*

#### cURL Example

```bash
curl -X POST https://dashboard.csitabmc.com/api/push-devices/register \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "token": "ExponentPushToken[example-device-token]",
    "platform": "android"
  }'
```

---

### 2.2 Unregister / Disable Device Token (Opt-Out)

Disables future push notifications for the specified device token when the user opts out.

- **URL**: `/api/push-devices/unregister`
- **Full URL**: `https://dashboard.csitabmc.com/api/push-devices/unregister`
- **Method**: `POST`
- **Auth**: None (Public)

#### Request Body (JSON)

| Field | Type | Required | Description |
|---|---|---|---|
| `token` | `string` | **Yes** | Expo Push Token to disable. |

```json
{
  "token": "ExponentPushToken[example-device-token]"
}
```

#### Successful Response

- **HTTP Status**: `200 OK`
- **Response Body**:
```json
{
  "success": true,
  "message": "Device unregistered"
}
```

> **Note**: This endpoint is completely **idempotent**. Calling it with an unknown token or a token that is already disabled will still return `HTTP 200 OK` with `{"success": true, "message": "Device unregistered"}`. The backend keeps the record with `enabled = false` to preserve opt-out state.

#### Error Responses

- **HTTP Status**: `400 Bad Request`
```json
{
  "error": "Push token is required",
  "details": {
    "token": ["Push token is required"]
  }
}
```

#### cURL Example

```bash
curl -X POST https://dashboard.csitabmc.com/api/push-devices/unregister \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "token": "ExponentPushToken[example-device-token]"
  }'
```

---

## 3. Client Implementation Notes

1. **Local Token Caching**:
   - The mobile app caches the current token under `csitabmc.pushToken` in `AsyncStorage`.
   - If the obtained Expo token matches the cached value, registration sync is skipped.
2. **Opt-Out Preference**:
   - When the user opts out of notifications in app settings, save the opt-out preference in `AsyncStorage` and call `/api/push-devices/unregister`.
   - If the user re-enables notifications later, calling `/api/push-devices/register` automatically re-enables the device in the backend (`enabled = true`).
3. **Trailing Slashes**:
   - The backend routes accept both `/api/push-devices/register` and `/api/push-devices/register/` (as well as `unregister`) without issuing HTTP redirects.
