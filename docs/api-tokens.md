# API tokens

The REST API accepts two kinds of credential:

- **Session** - the browser login. Used when you are signed in and viewing the
  site; the API works from the same session with no extra setup.
- **Token** - a 40-character key sent in a header. Used by a program that
  cannot fill in a login form, such as a camera or a script.

Both are checked on every request. A token is tried first, then the session.

## What a token does and does not do

A token says **who you are**. It does not say **what you may do**.

Permissions still come from the user's group. A token belonging to a Resident
is a valid credential, but the Resident group holds no API permissions, so
every restricted endpoint still answers 403. Issuing a token never widens
anyone's access.

| Response | Meaning |
|---|---|
| 401 Unauthorized | No credential, or the token is unknown. Authenticate first. |
| 403 Forbidden | Authenticated, but this user is not permitted here. |

## Issuing a token

Run on the server, as someone with shell access:

    python manage.py api_token issue <username>

The full key is printed **once**. It is never shown again, never written to a
file, and never returned by any endpoint. Store it in the client's own
configuration, somewhere not committed to version control.

The command refuses to issue a token to:

- an inactive account
- an account in the **Resident** group, which has no API permissions

## Checking and revoking

    python manage.py api_token show <username>      # first 8 characters only
    python manage.py api_token revoke <username>    # key stops working at once
    python manage.py api_token issue <username> --rotate   # replace the key

Rotating revokes the old key and issues a new one in a single step.

## Using a token

Send it on every request:

    Authorization: Token 0123456789abcdef0123456789abcdef01234567

With curl:

    curl -H "Authorization: Token <key>" http://127.0.0.1:8000/api/v1/vehicles/

Note the scheme word is `Token`, not `Bearer`.

## Tokens do not expire

DRF's default token has **no expiry date**. A key works until it is revoked.

This means:

- Revoke a token as soon as a client stops needing it.
- Rotate keys periodically rather than relying on expiry.
- Treat a leaked key as valid until you revoke it; revoke first, investigate after.

Adding expiry would need a different token implementation, such as JWT. That is
a deliberate future decision, not something the current setup provides.

## HTTPS

A token travels in a plain header. Over plain HTTP anyone who can see the
network traffic can read it and reuse it.

- **Local development on your own machine** - plain HTTP over `127.0.0.1` is
  acceptable; the traffic does not leave the computer.
- **Anything else** - a shared network, a test server, a real deployment -
  **requires HTTPS**. Without it, the token is exposed on every request.

The project's current settings have `DEBUG = True` and an empty
`ALLOWED_HOSTS`, which is a development configuration. Deployment hardening,
including HTTPS, is a separate step.

## Where tokens are stored

Tokens live in the `authtoken_token` table in plain text. This is how DRF's
default token model works. Anyone with database access can therefore read every
token, so the database must be protected accordingly.

## Endpoints and the permission each needs

| Endpoint | Method | Permission |
|---|---|---|
| `/api/v1/ping/` | GET | any signed-in user |
| `/api/v1/vehicles/` | GET | `vehicles.view_vehicle` |
| `/api/v1/vehicles/lookup/?plate=` | GET | `vehicles.view_vehicle` |
| `/api/v1/gate/logs/` | GET | `tracking.view_vehiclelog` |
| `/api/v1/gate/anpr-log/` | POST | `tracking.add_vehiclelog` |

Society Admin and Guard hold the permissions above. Resident holds none.

## CSRF

A session-authenticated POST from a browser needs a CSRF token, as any Django
form does. A token-authenticated POST does not, because a browser never attaches
an `Authorization` header by itself. This is the intended behaviour of both
schemes, not a gap in either.
