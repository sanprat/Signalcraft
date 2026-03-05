#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from pathlib import Path

token_hardcoded = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzcyNDQ0MjgzLCJpYXQiOjE3NzIzNTc4ODMsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTEwNTU3ODk2In0.WK6asDPtQ1q0yA9yvmNE5IN6ZvF-JNorZYAtyeKPt05HkzFTA-jIRPel5A0V57ACQDEB3g1WZweNpUCO8sDMcg"

load_dotenv(dotenv_path=Path("/Users/sanim/Downloads/sunny/Python/AIML/Pybankers/Pytrader/.env"))
token_env = os.getenv("DHAN_ACCESS_TOKEN")

print(f"Hardcoded length: {len(token_hardcoded)}")
print(f"Env length: {len(token_env)}")
print(f"Match: {token_hardcoded == token_env}")

if token_hardcoded != token_env:
    print("\nTokens differ!")
    for i, (a, b) in enumerate(zip(token_hardcoded, token_env)):
        if a != b:
            print(f"  First diff at position {i}: '{a}' vs '{b}'")
            print(f"  Context: ...{token_hardcoded[max(0,i-10):i+10]}...")
            print(f"  Context: ...{token_env[max(0,i-10):i+10]}...")
            break
else:
    print("\nTokens are identical!")
