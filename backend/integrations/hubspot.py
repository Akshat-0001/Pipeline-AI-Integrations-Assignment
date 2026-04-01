import json
import os
import secrets
import base64
from urllib.parse import urlencode
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import requests
from dotenv import load_dotenv

from integrations.integration_item import IntegrationItem
from redis_client import add_key_value_redis, get_value_redis, delete_key_redis

load_dotenv()

CLIENT_ID = os.getenv('HUBSPOT_CLIENT_ID', 'XXX')
CLIENT_SECRET = os.getenv('HUBSPOT_CLIENT_SECRET', 'XXX')
REDIRECT_URI = 'http://localhost:8000/integrations/hubspot/oauth2callback'
SCOPES = os.getenv('HUBSPOT_SCOPES', 'oauth crm.objects.contacts.read crm.objects.companies.read crm.objects.deals.read')


async def authorize_hubspot(user_id, org_id):
    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id,
    }
    encoded_state = base64.urlsafe_b64encode(json.dumps(state_data).encode('utf-8')).decode('utf-8')
    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', json.dumps(state_data), expire=600)

    params = urlencode({
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'scope': SCOPES,
        'state': encoded_state,
    })
    return f'https://app.hubspot.com/oauth/authorize?{params}'


async def oauth2callback_hubspot(request: Request):
    if request.query_params.get('error'):
        detail = request.query_params.get('error_description') or request.query_params.get('error')
        raise HTTPException(status_code=400, detail=detail)

    code = request.query_params.get('code')
    encoded_state = request.query_params.get('state')
    if not code or not encoded_state:
        raise HTTPException(status_code=400, detail='Missing code or state.')

    state_data = json.loads(base64.urlsafe_b64decode(encoded_state).decode('utf-8'))
    original_state = state_data.get('state')
    user_id = state_data.get('user_id')
    org_id = state_data.get('org_id')

    saved_state = await get_value_redis(f'hubspot_state:{org_id}:{user_id}')
    if not saved_state or original_state != json.loads(saved_state).get('state'):
        raise HTTPException(status_code=400, detail='State does not match.')

    async with httpx.AsyncClient() as client:
        response = await client.post(
            'https://api.hubapi.com/oauth/v1/token',
            data={
                'grant_type': 'authorization_code',
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'redirect_uri': REDIRECT_URI,
                'code': code,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )

    await delete_key_redis(f'hubspot_state:{org_id}:{user_id}')

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail='Failed to retrieve HubSpot tokens.')

    await add_key_value_redis(f'hubspot_credentials:{org_id}:{user_id}', json.dumps(response.json()), expire=600)

    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)


async def get_hubspot_credentials(user_id, org_id):
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')

    credentials = json.loads(credentials)
    await delete_key_redis(f'hubspot_credentials:{org_id}:{user_id}')
    return credentials


def create_integration_item_metadata_object(response_json, item_type):
    properties = response_json.get('properties', {})

    if item_type == 'contact':
        first_name = properties.get('firstname', '')
        last_name = properties.get('lastname', '')
        full_name = f'{first_name} {last_name}'.strip()
        name = full_name or properties.get('email') or response_json.get('id')
    elif item_type == 'company':
        name = properties.get('name') or properties.get('domain') or response_json.get('id')
    else:
        name = properties.get('dealname') or response_json.get('id')

    return IntegrationItem(
        id=response_json.get('id'),
        type=item_type,
        name=name,
        creation_time=properties.get('createdate'),
        last_modified_time=properties.get('hs_lastmodifieddate'),
    )


async def get_items_hubspot(credentials):
    credentials = json.loads(credentials)
    access_token = credentials.get('access_token')
    if not access_token:
        raise HTTPException(status_code=400, detail='No access token found.')

    items = []
    headers = {'Authorization': f'Bearer {access_token}'}
    object_configs = [
        ('contacts', 'contact', 'firstname,lastname,email,createdate,hs_lastmodifieddate'),
        ('companies', 'company', 'name,domain,createdate,hs_lastmodifieddate'),
        ('deals', 'deal', 'dealname,createdate,hs_lastmodifieddate'),
    ]

    for object_name, item_type, properties in object_configs:
        url = f'https://api.hubapi.com/crm/v3/objects/{object_name}'
        after = None

        while True:
            params = {
                'limit': 100,
                'properties': properties,
            }
            if after is not None:
                params['after'] = after

            response = requests.get(url, headers=headers, params=params)
            if response.status_code != 200:
                if response.status_code == 403:
                    raise HTTPException(
                        status_code=400,
                        detail='Insufficient HubSpot scopes. Enable crm.objects.contacts.read, crm.objects.companies.read, and crm.objects.deals.read for item loading.',
                    )
                raise HTTPException(status_code=400, detail='Failed to load HubSpot items.')

            data = response.json()
            for result in data.get('results', []):
                items.append(create_integration_item_metadata_object(result, item_type))

            after = data.get('paging', {}).get('next', {}).get('after')
            if not after:
                break

    return items