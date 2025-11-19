# Google Authentication - Frontend Integration Guide

## Overview

Your backend now supports receiving Google ID tokens directly from the frontend using the One Tap sign-in or Sign In With Google button.

## Endpoint

**POST** `/api/auth/google-login`

### Request Body
```json
{
  "credential": "eyJhbGciOiJSUzI1NiIsImtpZCI6IjI3M..."
}
```

### Response (Success - 200)
```json
{
  "email": "user@example.com",
  "name": "John Doe",
  "picture": "https://lh3.googleusercontent.com/a/...",
  "token": "your.application.jwt.token"
}
```

### Response (Error - 400/401/500)
```json
{
  "error": "Invalid Google token"
}
```

## Frontend Implementation Examples

### 1. Using Google One Tap (Recommended)

```html
<!DOCTYPE html>
<html>
<head>
  <script src="https://accounts.google.com/gsi/client" async defer></script>
</head>
<body>
  <div id="g_id_onload"
       data-client_id="YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com"
       data-callback="handleCredentialResponse">
  </div>
  <div class="g_id_signin" data-type="standard"></div>

  <script>
    async function handleCredentialResponse(response) {
      console.log("Encoded JWT ID token: " + response.credential);
      
      try {
        // Send the credential to your backend
        const result = await fetch('/api/auth/google-login', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            credential: response.credential
          })
        });

        const data = await result.json();

        if (result.ok) {
          console.log('Login successful!');
          console.log('Email:', data.email);
          console.log('Name:', data.name);
          console.log('Picture:', data.picture);
          console.log('Your App Token:', data.token);

          // Store the token for future API calls
          localStorage.setItem('app_token', data.token);
          
          // Store user info
          localStorage.setItem('user', JSON.stringify({
            email: data.email,
            name: data.name,
            picture: data.picture
          }));

          // Redirect to dashboard or update UI
          window.location.href = '/dashboard';
        } else {
          console.error('Login failed:', data.error);
          alert('Login failed: ' + data.error);
        }
      } catch (error) {
        console.error('Error during login:', error);
        alert('An error occurred during login');
      }
    }
  </script>
</body>
</html>
```

### 2. Using React

```jsx
import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google';

function LoginPage() {
  const handleGoogleLogin = async (credentialResponse) => {
    try {
      const response = await fetch('/api/auth/google-login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          credential: credentialResponse.credential
        })
      });

      const data = await response.json();

      if (response.ok) {
        // Store token and user info
        localStorage.setItem('app_token', data.token);
        localStorage.setItem('user', JSON.stringify({
          email: data.email,
          name: data.name,
          picture: data.picture
        }));

        // Navigate to dashboard
        console.log('Login successful!', data);
      } else {
        console.error('Login failed:', data.error);
      }
    } catch (error) {
      console.error('Error during login:', error);
    }
  };

  return (
    <GoogleOAuthProvider clientId="YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com">
      <div>
        <h1>Login</h1>
        <GoogleLogin
          onSuccess={handleGoogleLogin}
          onError={() => {
            console.log('Login Failed');
          }}
        />
      </div>
    </GoogleOAuthProvider>
  );
}

export default LoginPage;
```

### 3. Using Vanilla JavaScript with Google Sign-In Button

```javascript
function onSignIn(googleUser) {
  const id_token = googleUser.getAuthResponse().id_token;
  
  fetch('/api/auth/google-login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      credential: id_token
    })
  })
  .then(response => response.json())
  .then(data => {
    if (data.token) {
      // Success!
      localStorage.setItem('app_token', data.token);
      localStorage.setItem('user_email', data.email);
      localStorage.setItem('user_name', data.name);
      localStorage.setItem('user_picture', data.picture);
      
      // Redirect or update UI
      window.location.href = '/dashboard';
    } else {
      console.error('Login failed:', data.error);
    }
  })
  .catch(error => {
    console.error('Error:', error);
  });
}
```

## Using the Token for Authenticated Requests

After login, use the returned JWT token for authenticated API calls:

```javascript
// Example: Fetch user data
async function fetchUserData() {
  const token = localStorage.getItem('app_token');
  
  const response = await fetch('/api/user/profile', {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
  
  if (response.ok) {
    const data = await response.json();
    return data;
  } else {
    // Token might be expired
    console.error('Failed to fetch user data');
    // Redirect to login
  }
}
```

## Security Notes

1. **HTTPS Required**: Google ID tokens should only be sent over HTTPS in production
2. **Client ID**: Make sure to set `GOOGLE_CLIENT_ID` in your backend environment variables
3. **Token Storage**: Store the JWT token securely (httpOnly cookies are recommended for production)
4. **Token Expiration**: The JWT token expires based on your `JWT_EXP_DAYS` setting (default: 7 days)
5. **Email Verification**: The backend checks that the email is verified by Google

## Environment Variables Required

```bash
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
JWT_SECRET=your-secret-key-for-signing-jwts
JWT_EXP_DAYS=7  # Optional, defaults to 7
```

## What Happens in the Backend

1. Receives the Google ID token from frontend
2. Verifies the token with Google's servers
3. Extracts user information (email, name, picture)
4. Creates or updates user in MongoDB
5. Generates your application's JWT token
6. Returns user info + your JWT token

## Decoded Google ID Token Structure

The Google ID token contains (among other fields):
```json
{
  "iss": "https://accounts.google.com",
  "sub": "1234567890",  // Google user ID
  "email": "user@example.com",
  "email_verified": true,
  "name": "John Doe",
  "picture": "https://lh3.googleusercontent.com/a/...",
  "given_name": "John",
  "family_name": "Doe",
  "iat": 1234567890,
  "exp": 1234571490
}
```

Your backend verifies this token and uses the information to create/update the user.
