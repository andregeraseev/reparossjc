LABELS = {
    "home": "Início", "jobs": "Atendimentos", "job": "Ficha", "agenda": "Agenda",
    "quotes": "Orçamentos", "management": "Gestão", "settings": "Ajustes",
    "clients": "Clientes", "inventory": "Estoque", "materials": "Materiais",
    "schedule": "Agendamento", "session": "Sessão de trabalho", "payment": "Recebimento",
    "expenses": "Despesas", "pdf": "PDF", "assistant": "Assistente",
    "training": "Treinamento", "scope": "Escopo", "backup": "Backup",
    "save_jobs": "Atendimentos", "save_clients": "Clientes", "save_quotes": "Orçamentos",
    "save_inventory": "Estoque", "save_payments": "Recebimentos", "save_expenses": "Despesas",
    "save_sessions": "Sessões de trabalho", "save_materials": "Movimentações de estoque",
    "app_error": "Erro do aplicativo",
    "new_job": "Criar atendimento", "new_quote": "Criar orçamento",
    "edit_client": "Editar cliente", "search": "Usar busca",
    "save_schedule": "Salvar agendamento", "edit_scope": "Editar escopo",
    "start_work": "Iniciar serviço", "finish_work": "Concluir serviço",
    "edit_session": "Editar sessão de trabalho", "add_material": "Adicionar material",
    "edit_payment": "Editar recebimento", "remove_payment": "Excluir recebimento",
    "undo_payment": "Desfazer exclusão de recebimento", "edit_expense": "Editar despesa",
    "build_pdf": "Gerar ou abrir PDF", "use_voice": "Acionar ditado",
    "add_photo": "Acionar foto", "switch_tab": "Trocar de aba",
    "open_bug": "Abrir relato", "app_resume": "Voltar ao aplicativo",
    "app_pause": "Sair do primeiro plano",
}
ORIGINAL_SCREENS = {"home", "jobs", "job", "agenda", "quotes", "management", "settings"}
SCREENS = ORIGINAL_SCREENS | {"clients", "inventory", "materials", "schedule", "session",
    "payment", "expenses", "pdf", "assistant", "training", "scope", "backup"}
ORIGINAL_WRITES = {"save_jobs", "save_clients", "save_quotes", "save_inventory", "save_payments", "save_expenses"}
WRITES = ORIGINAL_WRITES | {"save_sessions", "save_materials"}
ACTIONS = set(LABELS) - SCREENS - WRITES - {"app_error"}
MAX_DURATION = 24 * 60 * 60
LIMITS = {1: 160, 2: 500}


def integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def events_valid(events, protocol, limit, duration=MAX_DURATION):
    if not isinstance(events, list) or len(events) > limit:
        return False
    screens, writes, actions = ((ORIGINAL_SCREENS, ORIGINAL_WRITES, set()) if protocol == 1 else (SCREENS, WRITES, ACTIONS))
    previous = 0
    for event in events:
        required = {"step", "result", "at"}
        if not isinstance(event, dict) or event.keys() not in (required, required | {"ms"}):
            return False
        step = event["step"]
        if not isinstance(step, str) or not integer(event["at"], previous, duration):
            return False
        accepted = ("opened",) if step in screens else ("acted",) if step in actions else ("failed",) if step == "app_error" else (
            ("verified", "failed") if step in writes else ()
        )
        if event["result"] not in accepted:
            return False
        if "ms" in event and (step not in writes or not integer(event["ms"], 0, 60000)):
            return False
        previous = event["at"]
    return True


def event_rows(events):
    return [{**event, "label": LABELS.get(event["step"], event["step"])} for event in events]
