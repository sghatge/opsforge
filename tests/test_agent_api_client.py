import json
import unittest
from unittest.mock import patch
from opsforge.agent_api_client import AgentAPIClient, AgentAPIError

class FakeResponse:
    def __init__(self, value):
        self.raw = json.dumps(value).encode()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size=-1):
        return self.raw[:size]

class AgentAPIClientTests(unittest.TestCase):
    def test_rejects_remote_plain_http(self):
        with self.assertRaises(AgentAPIError):
            AgentAPIClient("http://example.com", "x" * 40)

    def test_unknown_agent_never_calls_network(self):
        client = AgentAPIClient("http://127.0.0.1:8765", "x" * 40)
        with patch("opsforge.agent_api_client.urlopen") as call:
            with self.assertRaises(AgentAPIError):
                client.run_agent("send_campaign", {})
            call.assert_not_called()

    def test_requires_long_token(self):
        with self.assertRaises(AgentAPIError):
            AgentAPIClient("http://127.0.0.1:8765", "short").run_agent("research", {})

    def test_rejects_non_object_task(self):
        with self.assertRaises(AgentAPIError):
            AgentAPIClient("http://127.0.0.1:8765", "x" * 40).run_agent("research", [])

    def test_rejects_oversized_task(self):
        with self.assertRaises(AgentAPIError):
            AgentAPIClient("http://127.0.0.1:8765", "x" * 40).run_agent("research", {"x": "a" * 66000})

    def test_posts_allowlisted_agent_with_bearer_auth(self):
        client = AgentAPIClient("http://127.0.0.1:8765", "t" * 40)
        with patch("opsforge.agent_api_client.urlopen", return_value=FakeResponse({"status": "completed"})) as call:
            result = client.run_agent("research", {"question": "test"})
        request = call.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8765/api/agents/research/run")
        self.assertEqual(request.get_header("Authorization"), "Bearer " + "t" * 40)
        self.assertEqual(result["status"], "completed")

    def test_health_is_public_read_only(self):
        client = AgentAPIClient("http://127.0.0.1:8765")
        with patch("opsforge.agent_api_client.urlopen", return_value=FakeResponse({"status": "healthy"})) as call:
            result = client.health()
        self.assertEqual(call.call_args.args[0].get_method(), "GET")
        self.assertEqual(result["status"], "healthy")

if __name__ == "__main__":
    unittest.main()
