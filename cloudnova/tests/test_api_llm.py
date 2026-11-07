import httpx
from fastapi.testclient import TestClient

from app.api import app
from app.llm.provider import QwenProvider, set_provider_override


def test_api_ask_health_and_errors():
    c = TestClient(app)
    assert c.get("/health").json()["data"]["invoices"] == 5000
    r = c.post("/ask", json={"question": "How much have we given back in refunds?"})
    body = r.json()
    assert r.status_code == 200 and body["schema_version"] == "1.0" and body["result"]["rows"][0][0] == -8925163.8
    assert c.post("/ask", json={"question": ""}).status_code == 422
    assert c.post("/ask", json={"question": "hello"}).json()["code"] == "llm_unavailable"
    assert c.get("/api/kpis").json()["invoices"] == 5000
    assert len(c.get("/api/dashboard").json()["top_accounts"]["rows"]) == 10
    assert c.get("/api/data-quality").json()["manifest"]["rejected_rows"] == 125
    assert c.get("/").status_code == 200


def test_qwen_provider_against_fake_openai_server():
    def handler(req: httpx.Request):
        assert req.url.path.endswith("/chat/completions")
        return httpx.Response(200, json={"model": "qwen2.5-coder:3b", "choices": [{"message": {"content": "```sql\nSELECT 1\n```"}}],
                                         "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
    set_provider_override(None)
    p = QwenProvider(client=httpx.Client(transport=httpx.MockTransport(handler)))
    r = p.complete("sys", [{"role": "user", "content": "q"}])
    assert r.text.startswith("```sql") and r.input_tokens == 10


def test_text_to_sql_path_with_scripted_model():
    from app.agent import supervisor

    class Scripted:
        name, model = "qwen", "scripted"
        calls = 0

        def complete(self, system, messages, max_tokens=None, temperature=0.0):
            from app.llm.provider import LLMResponse
            Scripted.calls += 1
            if "translate questions" in system:
                # first attempt is unsafe → guard rejects → retry gets a safe query
                sql = "DROP TABLE invoices" if Scripted.calls == 1 else "SELECT industry, AVG(support_tickets) AS avg_tickets FROM invoices GROUP BY industry"
                return LLMResponse(text=f"```sql\n{sql}\n```", model=self.model)
            return LLMResponse(text="Tickets average 999999 per account.", model=self.model)  # ungrounded → rejected

        def ping(self):
            return {"reachable": True, "models": ["scripted"]}

    set_provider_override(Scripted())
    r = supervisor.ask("average support tickets by industry")
    assert r["planner"] == "llm_sql" and "DROP" not in r["sql"] and len(r["result"]["rows"]) >= 10
    assert "999999" not in r["answer"]  # ungrounded narrative replaced by deterministic table text
    assert any("ungrounded" in t["detail"] for t in r["trace"])
