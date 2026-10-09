"""Inspect installed ecdsa and diskcache callers. Prints names, not source."""

from __future__ import annotations

import ast
import importlib
import importlib.metadata
import importlib.util
from pathlib import Path

import jose.jws as jws
from jose.backends import ecdsa_backend
from jose.constants import ALGORITHMS


def _names(function: object) -> list[str]:
    code = getattr(function, "__code__", None)
    if code is None:
        return []
    return sorted(code.co_names)


print("HS256", ALGORITHMS.HS256)
print("ES256", ALGORITHMS.ES256)
print("ECDSA_BACKEND", ecdsa_backend.__name__)
print("JWS_SIGN_NAMES", ",".join(name for name in _names(jws.sign) if "ecdsa" in name.lower() or "hmac" in name.lower() or name in {"ALGORITHMS", "get_algorithm"}))
print("JWS_VERIFY_NAMES", ",".join(name for name in _names(jws.verify) if "ecdsa" in name.lower() or "hmac" in name.lower()))
if hasattr(jws, "get_algorithm"):
    for algorithm_name in ("HS256", "ES256"):
        selected = jws.get_algorithm(algorithm_name)
        print("ALGORITHM_BACKEND", algorithm_name, type(selected).__module__ + "." + type(selected).__name__)

hmac_module = importlib.import_module("jose.backends.cryptography_backend")
hmac_names = [name for name in dir(hmac_module) if name.endswith("Key")]
ecdsa_names = [name for name in dir(ecdsa_backend) if name.endswith("Key") or "EC" in name]
print("HMAC_KEY_CLASSES", ",".join(hmac_names))
print("ECDSA_KEY_CLASSES", ",".join(ecdsa_names))
if hmac_names:
    print("HMAC_KEY_MODULE", getattr(hmac_module, hmac_names[0]).__module__)
if ecdsa_names:
    print("ECDSA_KEY_MODULE", getattr(ecdsa_backend, ecdsa_names[0]).__module__)

llama = importlib.import_module("llama_cpp")
root = Path(llama.__file__).resolve().parent
print("LLAMA_ROOT", root.name)
for path in sorted(root.rglob("*.py")):
    text = path.read_text(encoding="utf-8", errors="ignore")
    flags = []
    if "diskcache" in text:
        flags.append("diskcache")
    if "pickle" in text:
        flags.append("pickle")
    if flags:
        print("LLAMA_FILE", path.relative_to(root).as_posix(), ",".join(flags))

llama_py = (root / "llama.py").read_text(encoding="utf-8")
tree = ast.parse(llama_py)
imports_cache = False
cache_calls = 0
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        imports_cache = imports_cache or any(alias.name == "llama_cpp.llama_cache" or alias.name.endswith("llama_cache") for alias in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module and "llama_cache" in node.module:
        imports_cache = True
    elif isinstance(node, ast.Call):
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if name in {"Cache", "LlamaDiskCache", "DiskCache"}:
            cache_calls += 1
print("LLAMA_PY_IMPORTS_LLAMA_CACHE", imports_cache)
print("LLAMA_PY_CACHE_CALLS", cache_calls)

cache_path = root / "llama_cache.py"
cache_tree = ast.parse(cache_path.read_text(encoding="utf-8"))
cache_imports = []
for node in cache_tree.body:
    if isinstance(node, ast.Import):
        cache_imports.extend(alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module:
        cache_imports.append(node.module)
print("LLAMA_CACHE_IMPORTS", ",".join(sorted(set(cache_imports))))
class_names = [node.name for node in cache_tree.body if isinstance(node, ast.ClassDef)]
print("LLAMA_CACHE_CLASSES", ",".join(class_names))
referenced = [name for name in class_names if name in llama_py]
print("LLAMA_PY_REFERENCES_CACHE_CLASSES", ",".join(referenced) or "none")
diskcache_calls = 0
for node in ast.walk(cache_tree):
    if isinstance(node, ast.Call):
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name == "Cache":
            diskcache_calls += 1
print("LLAMA_CACHE_CONSTRUCTS_DISKCACHE", diskcache_calls)
for node in cache_tree.body:
    if not isinstance(node, ast.ClassDef):
        continue
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name == "Cache":
                print("DISKCACHE_CONSTRUCTOR_CLASS", node.name)
llama_classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
print("LLAMA_PY_CLASS_COUNT", len(llama_classes))
print("LLAMA_PY_HAS_LLAMA_CLASS", "Llama" in llama_classes)
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == "Llama":
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                args = item.args.args
                defaults = item.args.defaults
                paired = list(zip(args[-len(defaults):], defaults, strict=True)) if defaults else []
                for arg, default in paired:
                    if "cache" in arg.arg and default is not None:
                        rendered = getattr(default, "id", None) or getattr(default, "attr", None) or ast.dump(default)
                        print("LLAMA_INIT_CACHE_DEFAULT", arg.arg, rendered)
                kw_defaults = item.args.kw_defaults or []
                for arg, default in zip(item.args.kwonlyargs, kw_defaults, strict=False):
                    if "cache" in arg.arg and default is not None:
                        rendered = getattr(default, "id", None) or getattr(default, "attr", None) or ast.dump(default)
                        print("LLAMA_INIT_CACHE_DEFAULT", arg.arg, rendered)
                uses = []
                for child in ast.walk(item):
                    if isinstance(child, ast.Assign):
                        for target in child.targets:
                            name = getattr(target, "attr", None) or getattr(target, "id", "")
                            if "cache" in str(name).lower():
                                value = getattr(child.value, "id", None) or getattr(child.value, "attr", None) or type(child.value).__name__
                                uses.append(f"{name}={value}")
                    elif isinstance(child, ast.Call):
                        func = child.func
                        name = getattr(func, "attr", None) or getattr(func, "id", "")
                        if name in class_names or "cache" in str(name).lower():
                            uses.append("call:" + str(name))
                print("LLAMA_INIT_CACHE_USES", ",".join(uses) or "none")
print("ECDSA_VERSION", importlib.metadata.version("ecdsa"))
print("DISKCACHE_VERSION", importlib.metadata.version("diskcache"))
print("PYJWT_VERSION", importlib.metadata.version("pyjwt"))
print("PYTHON_JOSE_VERSION", importlib.metadata.version("python-jose"))
print("MCP_SPEC_PRESENT", importlib.util.find_spec("mcp") is not None)
mcp_spec = importlib.util.find_spec("mcp")
if mcp_spec is not None and mcp_spec.origin:
    mcp_root = Path(mcp_spec.origin).resolve().parent
    jwt_files = []
    for path in mcp_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "import jwt" in text or "from jwt" in text:
            jwt_files.append(path.relative_to(mcp_root).as_posix())
    print("MCP_PACKAGE_JWT_FILES", ",".join(jwt_files) or "none")
    print("MCP_PACKAGE_VERSION", importlib.metadata.version("mcp"))
    credentials = mcp_root / "client" / "auth" / "extensions" / "client_credentials.py"
    credential_tree = ast.parse(credentials.read_text(encoding="utf-8"))
    jwt_calls = []
    algorithms = []
    for node in ast.walk(credential_tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name in {"encode", "decode"}:
                jwt_calls.append(name)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in {"HS256", "RS256", "ES256", "none"}:
            algorithms.append(node.value)
    print("MCP_CLIENT_JWT_CALLS", ",".join(sorted(set(jwt_calls))) or "none")
    print("MCP_CLIENT_JWT_ALGORITHMS", ",".join(sorted(set(algorithms))) or "none")
print("HS256_IN_HMAC", ALGORITHMS.HS256 in ALGORITHMS.HMAC)
print("HS256_IN_EC", ALGORITHMS.HS256 in ALGORITHMS.EC)
print("ES256_IN_EC", ALGORITHMS.ES256 in ALGORITHMS.EC)
print("API_ACTIVE_CHECK")
