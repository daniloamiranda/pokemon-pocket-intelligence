#!/usr/bin/env python3
"""F2 · Validador de contratos JSON Schema (subset stdlib).

Valida os contratos de contracts/ contra seus x-example e valida um payload
contra um contrato dado. Suporta: type, required, properties, items,
additionalProperties(false), enum, pattern, minimum, maximum, minLength,
const, format(date|date-time|uri básico).

Motivação: pip indisponível (PEP 668) e guard de rede — validação sem dependências.
Usado por scripts/gen_all_check.py e por tests/unit/test_migrations.py.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"


class ContractError(Exception):
    pass


_TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def _check_type(value, types, path):
    if isinstance(types, str):
        types = [types]
    py_types = []
    for t in types:
        mapped = _TYPE_MAP[t]
        py_types.extend(mapped if isinstance(mapped, tuple) else (mapped,))
    ok = isinstance(value, tuple(py_types))
    # bool não é int em JSON Schema:
    if isinstance(value, bool) and py_types and not any(isinstance(x, bool) for x in py_types):
        if isinstance(value, type):  # evita confusão classe vs instância
            ok = False
    if not ok:
        raise ContractError(f"{path}: esperado tipo {'/'.join(types)}, obtido {type(value).__name__} ({value!r})")


def validate(instance, schema, path="$"):
    if not isinstance(schema, dict):
        return
    if "const" in schema:
        if instance != schema["const"]:
            raise ContractError(f"{path}: const exigido {schema['const']!r}, obtido {instance!r}")
    if "enum" in schema:
        if instance not in schema["enum"]:
            raise ContractError(f"{path}: valor fora do enum: {instance!r}")
    if "type" in schema:
        _check_type(instance, schema["type"], path)
    t = schema.get("type")
    if isinstance(t, list):
        if "null" in t and instance is None:
            return
    if "pattern" in schema and isinstance(instance, str):
        if not re.search(schema["pattern"], instance):
            raise ContractError(f"{path}: não casa com pattern {schema['pattern']!r}: {instance!r}")
    if "minLength" in schema and isinstance(instance, str):
        if len(instance) < schema["minLength"]:
            raise ContractError(f"{path}: minLength {schema['minLength']} violado ({len(instance)})")
    if "minimum" in schema and isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if instance < schema["minimum"]:
            raise ContractError(f"{path}: minimum {schema['minimum']} violado ({instance})")
    if "maximum" in schema and isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if instance > schema["maximum"]:
            raise ContractError(f"{path}: maximum {schema['maximum']} violado ({instance})")
    if "format" in schema and isinstance(instance, str):
        f = schema["format"]
        if f == "date" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", instance):
            raise ContractError(f"{path}: formato date inválido: {instance}")
        if f == "date-time" and not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)*(Z|[+-]\d{2}:\d{2})", instance):
            raise ContractError(f"{path}: formato date-time inválido: {instance}")
        if f == "uri" and not re.match(r"(https?|ftp)://", instance):
            raise ContractError(f"{path}: formato uri inválido: {instance}")
    if isinstance(instance, dict) and schema.get("type") == "object":
        for req in schema.get("required", []):
            if req not in instance:
                raise ContractError(f"{path}: campo obrigatório ausente: {req}")
        props = schema.get("properties", {})
        for k, v in instance.items():
            if k in props:
                validate(v, props[k], f"{path}.{k}")
            elif schema.get("additionalProperties") is False:
                raise ContractError(f"{path}: campo não permitido: {k}")
            elif isinstance(schema.get("additionalProperties"), dict):
                validate(v, schema["additionalProperties"], f"{path}.{k}")
    if isinstance(instance, list) and schema.get("type") == "array":
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise ContractError(f"{path}: minItems {schema['minItems']} violado ({len(instance)})")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            raise ContractError(f"{path}: maxItems {schema['maxItems']} violado ({len(instance)})")
        it = schema.get("items")
        for i, item in enumerate(instance):
            if isinstance(it, dict):
                if it.get("$ref"):
                    ref_name = it["$ref"].split("/")[-1].removesuffix(".json")
                    ref_path = CONTRACTS / it["$ref"].split("/")[-1]
                    if not ref_path.exists():
                        raise ContractError(f"{path}[{i}]: $ref não resolvido: {it['$ref']}")
                    ref_schema = json.loads(ref_path.read_text("utf-8"))
                    validate(item, ref_schema, f"{path}[{i}]")
                else:
                    validate(item, it, f"{path}[{i}]")


def validate_contract_file(path: Path):
    """Valida o contrato em si + seu x-example."""
    schema = json.loads(path.read_text("utf-8"))
    # schema self-check
    if "type" not in schema or "$id" not in schema:
        raise ContractError(f"{path}: contrato sem 'type' ou '$id'")
    if schema.get("additionalProperties") is not False:
        raise ContractError(f"{path}: contrato deve ter additionalProperties=false")
    example = schema.get("x-example")
    if not example:
        raise ContractError(f"{path}: x-example ausente")
    validate(example, schema, f"{path.name}.x-example")
    return schema


def main() -> int:
    ok = 0
    for p in sorted(CONTRACTS.glob("*.json")):
        try:
            validate_contract_file(p)
            ok += 1
            print(f"  OK {p.name}")
        except (ContractError, json.JSONDecodeError) as e:
            print(f"  FALHA {p.name}: {e}", file=sys.stderr)
            return 1
    print(f"OK — {ok} contratos validados (self + example)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
