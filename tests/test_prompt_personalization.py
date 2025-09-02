from src.prompt_personalization import build_personalized_prompt, generate_thread_id


def test_build_personalized_prompt_concat():
    base = "Sei un assistente."
    user_info = "Nome: Mario, Livello: Base"
    p = build_personalized_prompt(base, user_info)
    assert "Sei un assistente." in p
    assert "Nome: Mario" in p
    assert "Informazioni Utente Corrente" in p


def test_generate_thread_id_versioned():
    tid1 = generate_thread_id("user-1", 3)
    tid2 = generate_thread_id("user-1", 4)
    assert tid1 != tid2 and tid1.startswith("user-1:v3") and tid2.startswith("user-1:v4")


