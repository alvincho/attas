import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pytest
import time
import httpx

from prompits.tests.test_support import start_agent_thread, stop_servers


@pytest.fixture(scope="module")
def setup_config_agents():
    # Write to a clean log space or rely on default mailbox logging if we have to monitor it.
    # For alice and bob, we can just intercept the received chat or mailbox via HTTP polling or similar.
    # We will just verify the response for /mailbox since the agents provide one by default!

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../attas/configs'))
    plaza_cfg = os.path.join(base_dir, "plaza.agent")
    alice_cfg = os.path.join(base_dir, "alice.agent")
    bob_cfg = os.path.join(base_dir, "bob.agent")

    _, plaza_server, plaza_thread = start_agent_thread(plaza_cfg, log_level="info")
    _, alice_server, alice_thread = start_agent_thread(alice_cfg, log_level="info")
    _, bob_server, bob_thread = start_agent_thread(bob_cfg, log_level="info")
    
    # Wait for servers to start
    time.sleep(5)
    
    yield
    
    stop_servers([
        (plaza_server, plaza_thread),
        (alice_server, alice_thread),
        (bob_server, bob_thread)
    ])

@pytest.mark.asyncio
async def test_plaza_flow_via_config(setup_config_agents):
    async with httpx.AsyncClient() as client:
        alice_name = "alice_cfg_manual"
        bob_name = "bob_cfg_manual"

        # 1. Register Alice with a short expiry.
        # Use a small buffer to avoid timing flakes under slower backends/logging.
        resp = await client.post("http://127.0.0.1:8011/register", json={
            "agent_name": alice_name,
            "address": "http://127.0.0.1:8012",
            "expires_in": 3
        })
        assert resp.status_code == 200, f"Alice registration failed: {resp.text}"
        alice_data = resp.json()
        assert "token" in alice_data
        alice_token = alice_data["token"]
        print("Alice registered. Initial Token:", alice_token)
        
        # 2. Authenticate Alice immediately (before other calls can consume TTL)
        resp = await client.post("http://127.0.0.1:8011/authenticate", headers={"Authorization": f"Bearer {alice_token}"})
        assert resp.status_code == 200, f"Alice authentication failed: {resp.text}"
        print("Alice authenticated successfully with initial token.")

        # 3. Register Bob
        resp = await client.post("http://127.0.0.1:8011/register", json={
            "agent_name": bob_name,
            "address": "http://127.0.0.1:8013"
        })
        assert resp.status_code == 200, f"Bob registration failed: {resp.text}"
        print("Bob registered.")
        
        # Sleep long enough to ensure Alice's short-lived token expires.
        print("Sleeping to let Alice's token expire...")
        time.sleep(3.5)
        
        # 4. Authenticate Alice after expiry (Should Fail)
        resp = await client.post("http://127.0.0.1:8011/authenticate", headers={"Authorization": f"Bearer {alice_token}"})
        assert resp.status_code == 401, "Expected 401 Unauthorized for expired token"
        print("Alice authentication correctly failed after expiry.")
        
        # 5. Renew Alice's token
        # Notice we can still use the expired token in the header to renew assuming signature/existence matches!
        resp = await client.post("http://127.0.0.1:8011/renew", json={
            "agent_name": alice_name,
            "expires_in": 3600
        }, headers={"Authorization": f"Bearer {alice_token}"})
        assert resp.status_code == 200, f"Renew failed: {resp.text}"
        new_alice_token = resp.json()["token"]
        print("Alice renewed her token successfully:", new_alice_token)

        # 5.1 Heartbeat should accept current compact payload
        hb_resp = await client.post(
            "http://127.0.0.1:8011/heartbeat",
            json={"agent_name": alice_name},
            headers={"Authorization": f"Bearer {new_alice_token}"}
        )
        assert hb_resp.status_code == 200, f"Heartbeat failed: {hb_resp.text}"
        
        # 6. Relay Message from Alice to Bob using new token
        payload = {
            "receiver": bob_name,
            "content": "Hello Bob from Alice!",
            "msg_type": "chat-practice" 
        }
        
        print(f"Alice sending relay message payload.")
        resp = await client.post("http://127.0.0.1:8011/relay", json=payload, headers={"Authorization": f"Bearer {new_alice_token}"})
        
        print("Relay Response Code:", resp.status_code)
        print("Relay Response Text:", resp.text)
        assert resp.status_code == 200, "Relay failed with the new valid token"
