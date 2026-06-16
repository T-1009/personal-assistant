import asyncio
from app.main import app
from app.agent_handler import AgentHandler
from unittest.mock import patch, MagicMock
from app.tools import email_tools

async def run_test():
    handler = AgentHandler()
    q = asyncio.Queue()
    
    # We want to mock out identity_client to immediately call on_auth_url 
    # instead of doing a real request.
    from agentarts.sdk.service.identity.identity_client import IdentityClient
    original_get_token = IdentityClient.get_resource_oauth2_token

    async def mock_get_token(self, *, provider_name, scopes, workload_access_token, on_auth_url, auth_flow, callback_url, force_authentication, token_poller, custom_state, custom_parameters):
        print("MOCK get_resource_oauth2_token called")
        if on_auth_url:
            await on_auth_url("https://mock-auth-url")
            print("MOCK on_auth_url finished")
            # Return some fake token so we don't block
            return "fake-token"
        return "fake-token"

    IdentityClient.get_resource_oauth2_token = mock_get_token

    async for event in handler.handle_stream("帮我查邮件", "test_user", "test_session", q):
        print("SSE: " + event.strip())

if __name__ == "__main__":
    asyncio.run(run_test())
