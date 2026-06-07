from app.scenarios.ordering import (
    build_system_prompt, load_menu, load_menu_or_default, MenuItem, DEFAULT_MENU,
)


def test_load_menu_or_default_falls_back_when_missing(tmp_path):
    missing = str(tmp_path / "nope.json")
    assert load_menu_or_default(missing) == DEFAULT_MENU
    assert len(DEFAULT_MENU) > 0


def test_load_menu_or_default_reads_existing_file(tmp_path):
    p = tmp_path / "menu.json"
    p.write_text('[{"name":"Tea","price":"$2","desc":"green tea"}]', encoding="utf-8")
    items = load_menu_or_default(str(p))
    assert items == [MenuItem(name="Tea", price="$2", desc="green tea")]


def test_load_menu_returns_items(tmp_path):
    p = tmp_path / "menu.json"
    p.write_text('[{"name":"Latte","price":"$4","desc":"espresso + milk"}]', encoding="utf-8")
    items = load_menu(str(p))
    assert items[0] == MenuItem(name="Latte", price="$4", desc="espresso + milk")


def test_build_system_prompt_injects_menu():
    items = [MenuItem(name="Latte", price="$4", desc="espresso + milk")]
    prompt = build_system_prompt(items)
    assert "Latte" in prompt
    assert "waiter" in prompt.lower() or "server" in prompt.lower()
    # 终止目标(完成点餐)写进 prompt
    assert "goal" in prompt.lower() or "完成" in prompt
