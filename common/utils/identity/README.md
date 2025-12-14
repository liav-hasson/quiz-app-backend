# Identity and Authentication

This directory handles everything related to who the user is (Identity) and proving they are who they say they are (Authentication).

## The Auth Flow

We use a combination of Google Sign-In and our own JSON Web Tokens (JWT).

1. **Frontend Login**: The user clicks "Sign in with Google" on the frontend. Google gives them an ID Token.
2. **Backend Verification**: The frontend sends this Google ID Token to our backend.
3. **GoogleTokenVerifier**: We use `google_verifier.py` to ask Google, "Is this token valid?" and "Who does it belong to?".
4. **User Creation/Update**: If valid, we find the user in our database (or create a new one if it's their first time).
5. **Session Token**: We create our own JWT using `token_service.py`. This is the "Session Token".
6. **API Requests**: For all future requests, the frontend sends our Session Token. We verify this token to know who is making the request.

## Files

- **`google_verifier.py`**: Handles the communication with Google's servers to validate their tokens.
- **`token_service.py`**: Manages our own JWTs - creating them when a user logs in, and decoding them to check if a user is logged in.
