"""Reproduce the checkpoint fixtures and hidden checker inputs. Never seed this file."""
import base64
import json
from pathlib import Path
import yaml

ROOT = Path(__file__).parent / "tasks"


def make(tid, prompt, files, outputs, kind="bytes", command=None, schema=None):
    root = ROOT / tid
    root.mkdir(parents=True, exist_ok=True)
    fixture = root / "fixture"
    for name, content in files.items():
        path = fixture / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode() if isinstance(content, str) else content)
    (root / "task.yaml").write_text(yaml.safe_dump({"id": tid, "prompt": prompt}, allow_unicode=True), encoding="utf-8")
    outputs = {k: v.encode() if isinstance(v, str) else v for k, v in outputs.items()}
    encoded = {k: base64.b64encode(v).decode() for k, v in outputs.items()}
    expected = {"kind": kind, "outputs": encoded, "preserve_fixture": True}
    if schema:
        expected["schema"] = schema
    (root / "expected.json").write_text(json.dumps(expected, ensure_ascii=True, indent=2), encoding="utf-8")
    replay = [{"kind": "tool", "tool": "list", "args": "{}", "text": ""}]
    if command:
        replay.append({"kind": "tool", "tool": "exec", "args": json.dumps({"command": command}), "text": ""})
    for name, content in encoded.items():
        replay.append({"kind": "tool", "tool": "write", "args": json.dumps({"path": name, "content": content, "encoding": "base64"}), "text": ""})
    replay.append({"kind": "final", "tool": "none", "args": "{}", "text": "Synthetic replay completed; no model quality claim."})
    (root / "replay.json").write_text(json.dumps(replay, indent=2), encoding="utf-8")
    (root / "check.py").write_text('import json, sys\nfrom pathlib import Path\nfrom rah.baf_checks import check\nif __name__ == "__main__":\n    root = Path(sys.argv[1])\n    files = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file() and not p.is_symlink()}\n    passed, reason = check(Path(__file__).parent, files)\n    print(json.dumps({"pass": passed, "reason": reason}))\n', encoding="utf-8")


def main():
    original = Path(__file__).parent / "B1-read/B1.1-service-port/fixture"
    make("B1.1", "На каком порту слушает сервис? Запиши только число в answer.txt.", {p.relative_to(original).as_posix(): p.read_bytes() for p in original.rglob("*") if p.is_file()}, {"answer.txt": "8137\n"}, "answer")
    contract = "# Договор поставки\n" + "\n".join(f"## Страница {i}\nУсловия раздела {i}: поставка по согласованному графику.\n" + ("Срок оплаты — 37 календарных дней с даты приёмки.\n" if i == 12 else "Сроки отдельных поставок определяются заявкой.\n") for i in range(1, 16))
    make("B1.2", "Какой срок оплаты в днях по contract.md? Запиши число в answer.txt.", {"contract.md": contract}, {"answer.txt": "37"}, "answer")
    make("B1.3", "Какой размер неустойки по contract.md? Запиши в answer.txt. Если данных нет, напиши НЕТ ДАННЫХ.", {"contract.md": contract + "\nОтветственность регулируется применимым законодательством.\n"}, {"answer.txt": "НЕТ ДАННЫХ"}, "answer")
    make("B2.1", "В каком файле определена функция parse_date? Запиши относительный путь в answer.txt.", {"src/dateutil.py": "def parse_date(text):\n    return text.split('-')\n", "README.md": "The API uses parse_date.\n"}, {"answer.txt": "src/dateutil.py"}, "answer")
    files = {}
    reads = []
    for i in range(200):
        name = f"src/module_{i:03}.py"
        real = i % 17 == 0
        files[name] = "import os\nDB = os.environ.get('DB_URL')\n" if real else "# DB_URL is documented here, but is not read.\nVALUE = 1\n"
        if real:
            reads.append(name)
    make("B2.2", "Перечисли все файлы, где читается переменная окружения DB_URL. По одному относительному пути на строку в answer.txt. Комментарии не считаются.", files, {"answer.txt": "\n".join(reads)}, "set")
    make("B2.3", "Где функция, которая парсит даты ISO 8601 с таймзоной? Запиши относительный путь в answer.txt.", {"src/legacy.py": "from datetime import datetime\ndef parse_date(text):\n    return datetime.strptime(text, '%Y-%m-%d')\n", "src/iso.py": "from datetime import datetime\ndef parse_date(text):\n    return datetime.fromisoformat(text.replace('Z', '+00:00'))\n"}, {"answer.txt": "src/iso.py"}, "answer")
    schema = {"type": "object", "required": ["host", "port", "debug"], "additionalProperties": False, "properties": {"host": {"const": "localhost"}, "port": {"type": "integer", "const": 8137}, "debug": {"const": False}}}
    make("B3.1", "Создай config.json по spec.md.", {"spec.md": "Create JSON object: host string localhost, port integer 8137, debug boolean false. No other fields.\n"}, {"config.json": '{"host":"localhost","port":8137,"debug":false}\n'}, "json", schema=schema)
    make("B3.2", "Сделай report.csv из таблицы task.md, отсортируй по дате. Заголовок date,amount; LF, запятая, без пробелов.", {"task.md": "| date | amount |\n|---|---|\n|2026-03-02|7|\n|2026-01-03|11|\n|2026-02-10|4|\n"}, {"report.csv": "date,amount\n2026-01-03,11\n2026-02-10,4\n2026-03-02,7\n"})
    make("B3.3", "Создай countries.yaml и postal.yaml по task.md. Значения должны оставаться строками при YAML 1.1 чтении.", {"task.md": "countries.yaml mapping: norway -> NO, ontario -> ON. postal.yaml mapping: home -> 0123. Preserve strings.\n"}, {"countries.yaml": "norway: 'NO'\nontario: 'ON'\n", "postal.yaml": "home: '0123'\n"}, "yaml")
    readme = "# Demo\nVersion 1.2 is documented here.\n\n## Install\npip install demo==1.2\n\n## History\nRelease 1.2.\n"
    make("B4.1", "Обнови версию до 1.3 только в разделе Install README.md. Остальные байты сохрани.", {"README.md": readme}, {"README.md": readme.replace("demo==1.2", "demo==1.3")})
    code = {"calc.py": "def calc_total(items):\n    return sum(items)\n", "app.py": "from calc import calc_total\ndef run():\n    return calc_total([1, 2, 3])\n", "notes.md": "Unrelated file; preserve bytes.\n"}
    make("B4.2", "Переименуй calc_total в compute_total во всём Python-проекте; сохрани поведение и остальные файлы.", code, {k: v.replace("calc_total", "compute_total") for k, v in code.items() if k.endswith(".py")}, "rename")
    prices = "товар;цена\r\nX;1200\r\nY;450\r\n".encode("cp1251")
    make("B4.3", "Поменяй цену товара X на 990 в prices.csv. Сохрани исходную кодировку и переводы строк, остальные байты.", {"prices.csv": prices}, {"prices.csv": prices.replace(b"X;1200", b"X;990")})
    make("B5.1", "Запусти python stats.py data.csv и запиши медиану в answer.txt.", {"stats.py": "import csv, statistics, sys\nvalues = [int(row[0]) for row in csv.reader(open(sys.argv[1]))]\nprint(statistics.median(values))\n", "data.csv": "1\n9\n3\n7\n5\n"}, {"answer.txt": "5"}, "answer", command="python stats.py data.csv")
    tests = "import unittest\nclass Suite(unittest.TestCase):\n" + "".join(f"    def test_{i:02}(self):\n        self.assertEqual({i}, {i+1 if i in (3,9,17) else i})\n" for i in range(20)) + "if __name__ == '__main__':\n    unittest.main(verbosity=2)\n"
    make("B5.2", "Прогони тесты проекта командой python tests.py. Запиши короткие имена упавших тестов (test_XX) по одному на строку в failed.txt.", {"tests.py": tests}, {"failed.txt": "test_03\ntest_09\ntest_17\n"}, "set", command="python tests.py")
    make("B5.3", "Успешно ли отрабатывает build.sh? Запусти sh build.sh, запиши yes/no и причину в answer.txt.", {"build.sh": "#!/bin/sh\necho OK\necho 'dependency missing' >&2\nexit 1\n"}, {"answer.txt": "no: dependency missing (exit 1)\n"}, "build", command="sh build.sh")


if __name__ == "__main__":
    main()
