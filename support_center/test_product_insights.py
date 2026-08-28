from types import SimpleNamespace

from django.test import SimpleTestCase

from .product_ingest import sanitize_product_detail
from .product_insights import summarize_product_events


def event(operation, *, version="18.29", **detail):
    payload={"operation":operation, **detail}
    return SimpleNamespace(detail=payload, app_version=version)


class ProductMetadataSanitizerTests(SimpleTestCase):
    def test_keeps_only_bounded_product_metadata(self):
        raw={
            "operation":"ux_management_session",
            "screen":"management main",
            "feature":"next-action",
            "firstActionMs":1234,
            "backtrackCount":2,
            "usedQuick":True,
            "customerName":"Pessoa Privada",
            "speechText":"troquei a torneira do cliente",
            "amount":999.90,
        }
        clean=sanitize_product_detail(raw)
        self.assertEqual(clean["operation"], "ux_management_session")
        self.assertEqual(clean["screen"], "management_main")
        self.assertEqual(clean["feature"], "next-action")
        self.assertEqual(clean["firstActionMs"], 1234)
        self.assertEqual(clean["backtrackCount"], 2)
        self.assertIs(clean["usedQuick"], True)
        self.assertNotIn("customerName", clean)
        self.assertNotIn("speechText", clean)
        self.assertNotIn("amount", clean)

    def test_clamps_large_timing_values(self):
        clean=sanitize_product_detail({"operation":"ux_job_flow_session","completionMs":9999999999})
        self.assertEqual(clean["completionMs"], 86_400_000)


class ProductInsightsTests(SimpleTestCase):
    def test_aggregates_sessions_without_content(self):
        rows=[
            event("ux_management_session", outcome="actioned", firstActionMs=5000),
            event("ux_management_session", outcome="view_only", firstActionMs=0),
            event("ux_quote_session", outcome="shared"),
            event("ux_quote_search_zero", zeroResults=True),
            event("ux_job_flow_session", usedQuick=True, usedVoice=True, backtrackCount=1),
            event("ux_voice_result"),
            event("ux_management_slow_render", renderMs=180),
            event("not_product_event"),
        ]
        summary=summarize_product_events(rows)
        m=summary["metrics"]
        self.assertEqual(m["events"], 7)
        self.assertEqual(m["management_sessions"], 2)
        self.assertEqual(m["management_action_rate"], 50.0)
        self.assertEqual(m["management_first_action_ms"], 5000.0)
        self.assertEqual(m["quote_sessions"], 1)
        self.assertEqual(m["quote_share_rate"], 100.0)
        self.assertEqual(m["zero_searches"], 1)
        self.assertEqual(m["job_sessions"], 1)
        self.assertEqual(m["quick_register_rate"], 100.0)
        self.assertEqual(m["voice_job_rate"], 100.0)
        self.assertEqual(m["voice_results"], 1)
        self.assertEqual(m["slow_renders"], 1)

    def test_flags_repeated_friction_only_with_enough_sessions(self):
        rows=[]
        for _ in range(5):
            rows.append(event("ux_management_session", outcome="view_only", firstActionMs=0))
            rows.append(event("ux_quote_session", outcome="closed"))
            rows.append(event("ux_job_flow_session", usedQuick=False, usedVoice=False, backtrackCount=3))
        rows.extend(event("ux_quote_search_zero", zeroResults=True) for _ in range(2))
        summary=summarize_product_events(rows)
        titles={row["title"] for row in summary["signals"]}
        self.assertIn("Gestão ainda muito consultiva", titles)
        self.assertIn("Busca do catálogo merece revisão", titles)
        self.assertIn("Fluxo de atendimento tem retorno excessivo", titles)
        self.assertIn("Registro rápido pouco adotado", titles)
