import asyncio
import json
import sys

import httpx

from app.main import app


async def read_sse(response):
    events = []
    async for line in response.aiter_lines():
        if line.startswith("event: "):
            events.append(line[7:])
        elif line.startswith("data: ") and events:
            events[-1] = (events[-1], json.loads(line[6:]))
    return events


async def main():
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            username = "demo_user_1"
            r = await client.post("/api/v1/auth/register", json={"username": username, "password": "demo12345"})
            if r.status_code != 200:
                r = await client.post("/api/v1/auth/login", json={"username": username, "password": "demo12345"})
            print("auth", r.status_code, r.json()["code"])
            token = r.json()["data"]["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            r = await client.patch(
                "/api/v1/profiles/me",
                headers=headers,
                json={"birth_date": "1985-06-01", "sex": "male", "height_cm": 175, "weight_kg": 88},
            )
            print("profile", r.status_code, r.json()["data"]["bmi"])

            r = await client.post("/api/v1/conversations", headers=headers, json={})
            cid = r.json()["data"]["id"]
            print("conversation", cid)

            text = "我今年39岁，男，身高175，体重88公斤，血压150/95，每周运动1天，久坐9小时，睡眠6小时，口味重，吸烟"
            async with client.stream(
                "POST", f"/api/v1/conversations/{cid}/messages/stream", headers=headers, json={"content": text}
            ) as resp:
                events = await read_sse(resp)
            print("events1", [e[0] for e in events])
            confirm = [e[1] for e in events if e[0] == "confirmation_required"][0]
            print("confirm1", confirm["approval_type"], confirm["summary"])
            run_id = confirm["run_id"]

            async with client.stream(
                "POST",
                f"/api/v1/runs/{run_id}/resume/stream",
                headers=headers,
                json={"approval_type": "profile", "decision": "approve"},
            ) as resp:
                events = await read_sse(resp)
            print("events2", [e[0] for e in events])
            confirm = [e[1] for e in events if e[0] == "confirmation_required"]
            if confirm:
                confirm = confirm[0]
                print("confirm2", confirm["approval_type"], confirm["plan_id"], confirm["summary"])
                async with client.stream(
                    "POST",
                    f"/api/v1/runs/{run_id}/resume/stream",
                    headers=headers,
                    json={
                        "approval_type": "plan",
                        "decision": "approve",
                        "business_id": confirm["plan_id"],
                        "version_id": confirm["plan_version_id"],
                    },
                ) as resp:
                    events = await read_sse(resp)
                print("events3", [e[0] for e in events])
                print("reply", [e[1] for e in events if e[0] == "token"])

            r = await client.get("/api/v1/assessments/latest", headers=headers)
            data = r.json()["data"]
            print("assessment", data["overall_level"], data["urgency"], [d["level"] for d in data["dimensions"]])

            r = await client.get("/api/v1/plans", headers=headers)
            print("plans", r.json()["data"])

            r = await client.get("/api/v1/reports", headers=headers)
            print("reports", r.json()["data"])

            r = await client.get("/api/v1/reminders", headers=headers)
            print("reminders", len(r.json()["data"]))

            async with client.stream(
                "POST", f"/api/v1/conversations/{cid}/messages/stream", headers=headers, json={"content": "突然胸痛喘不上气"}
            ) as resp:
                events = await read_sse(resp)
            print("emergency", [e[0] for e in events], [e[1] for e in events if e[0] == "token"])

            r = await client.get("/api/v1/profiles/me/emergency-events", headers=headers)
            rows = r.json()["data"]
            print("emergency-events", r.status_code, len(rows), rows[0]["urgency"] if rows else None)

            r = await client.get("/api/v1/knowledge/sources", headers=headers)
            rows = r.json()["data"]
            print("knowledge-sources", r.status_code, len(rows), rows[0]["issuing_org"] if rows else None)


if __name__ == "__main__":
    asyncio.run(main())
