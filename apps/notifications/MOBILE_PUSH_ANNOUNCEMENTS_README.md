# CSITABMC Mobile App Push Notifications & Announcements Integration Guide

This guide is prepared for mobile application developers integrating Announcements and Notices push notifications.

---

## 1. Device Token Registration

The mobile app registers Expo Push Tokens using the standard endpoint:

- **Route:** `POST /api/push-devices/register`
- **Authentication:** Public (No Bearer token required)
- **Content-Type:** `application/json`

### Request Payload:
```json
{
  "token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
  "platform": "android" // or "ios"
}
```

### Response:
- **Status:** `201 Created` (first registration) or `200 OK` (token refreshed/re-enabled)
```json
{
  "id": 12,
  "token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
  "platform": "android",
  "enabled": true,
  "createdAt": "2026-11-02T10:00:00Z",
  "updatedAt": "2026-11-02T10:00:00Z"
}
```

---

## 2. Notification Types & Payload Shapes

When the CSITABMC CMS sends a push notification via Expo Push API, it includes a `data` JSON object to route the mobile user to the relevant screen when tapped.

### A. Announcement Notifications
- **Trigger:** Sent automatically when a CMS user publishes a new Announcement.
- **Expo Title:** Announcement Title
- **Expo Body:** Announcement Description (up to 2000 chars)

#### Notification `data` Payload:
```json
{
  "type": "announcement",
  "id": 45,
  "link": "https://csitabmc.com/events/annual-meet"
}
```

#### Mobile Tap Action:
- Read `response.notification.request.content.data`.
- If `type === "announcement"`:
  - If `link` is present and non-empty, prompt user or open external browser / in-app browser with `Linking.openURL(link)`.
  - Alternatively, navigate to `AnnouncementsDetailScreen({ id: data.id })`.

---

### B. Notice Notifications
- **Trigger:** Sent automatically when a Notice status transitions to `published` (newly published or draft published).
- **Expo Title:** Notice Title
- **Expo Body:** First 200 characters of Notice Description

#### Notification `data` Payload:
```json
{
  "type": "notice",
  "noticeId": "academic-calendar-2026" // Slug or string ID
}
```

#### Mobile Tap Action:
- Read `response.notification.request.content.data`.
- If `type === "notice"`:
  - Navigate directly to `NoticeDetailScreen({ idOrSlug: data.noticeId })`.

---

## 3. Public Announcements API (Mobile Client Read)

To fetch announcements in the mobile feed:

- **Route:** `GET /announcements/`
- **Authentication:** Public (No Bearer token required)
- **Query Parameters:**
  - `page`: Page number (default: 1)
  - `page_size`: Page size (default: 10)
  - `search`: Filter by title substring

### Response Example:
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 45,
      "title": "Annual Tech Symposium 2026",
      "description": "Registration is officially open for all students.",
      "image": "https://api.csitabmc.com/media/announcements/banner.webp",
      "link": "https://csitabmc.com/symposium",
      "createdAt": "2026-11-02T10:15:00Z",
      "updatedAt": "2026-11-02T10:15:00Z"
    }
  ]
}
```

---

## 4. React Native / Expo Notification Listener Implementation

```javascript
import * as Notifications from 'expo-notifications';
import { useEffect } from 'react';
import { Linking } from 'react-native';

export function useNotificationNavigation(navigationRef) {
  useEffect(() => {
    // Handle notification tap when app is in background / foreground / closed
    const subscription = Notifications.addNotificationResponseReceivedListener(response => {
      const data = response.notification.request.content.data;
      if (!data) return;

      if (data.type === 'announcement') {
        if (data.link) {
          Linking.openURL(data.link).catch(err => console.error("Couldn't open URL", err));
        } else {
          navigationRef.navigate('AnnouncementDetail', { id: data.id });
        }
      } else if (data.type === 'notice') {
        navigationRef.navigate('NoticeDetail', { noticeId: data.noticeId });
      }
    });

    return () => subscription.remove();
  }, []);
}
```

---

## 5. Token Hygiene & Invalidation

- If a user uninstalls the app or revokes permissions, Expo returns `DeviceNotRegistered`.
- The CSITABMC backend automatically detects this error code and disables the token (`enabled: false`) to prevent wasteful dispatches.
- When the app is re-installed or re-opened, calling `POST /api/push-devices/register` will automatically re-enable the device token for future notifications.
