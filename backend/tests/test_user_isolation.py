import requests
import uuid
import time

BASE_URL = "http://localhost:8001/api"

def test_isolation():
    # 1. Register User A
    email_a = f"user_a_{uuid.uuid4().hex[:4]}@test.com"
    pwd = "password123"
    print(f"Registering User A: {email_a}")
    resp = requests.post(f"{BASE_URL}/auth/register", json={
        "email": email_a,
        "password": pwd,
        "full_name": "User A"
    })
    assert resp.status_code == 200
    
    # 2. Register User B
    email_b = f"user_b_{uuid.uuid4().hex[:4]}@test.com"
    print(f"Registering User B: {email_b}")
    resp = requests.post(f"{BASE_URL}/auth/register", json={
        "email": email_b,
        "password": pwd,
        "full_name": "User B"
    })
    assert resp.status_code == 200

    # 3. Login A
    resp = requests.post(f"{BASE_URL}/auth/login", data={"username": email_a, "password": pwd})
    token_a = resp.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 4. Login B
    resp = requests.post(f"{BASE_URL}/auth/login", data={"username": email_b, "password": pwd})
    token_b = resp.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 5. Create Strategy as A
    print("Creating strategy as User A...")
    resp = requests.post(f"{BASE_URL}/strategy", json={
        "name": "User A Strategy",
        "symbol": "RELIANCE",
        "timeframe": "15minute",
        "entry_conditions": [],
        "exit_conditions": {}
    }, headers=headers_a)
    assert resp.status_code == 200
    strategy_id = resp.json()["strategy_id"]

    # 6. List Strategies as B
    print("Checking User B's strategy list (should be empty)...")
    resp = requests.get(f"{BASE_URL}/strategy", headers=headers_b)
    assert resp.status_code == 200
    assert len(resp.json()) == 0
    print("SUCCESS: User B cannot see User A's strategy list.")

    # 7. Try to fetch A's strategy as B
    print(f"Trying to fetch User A's strategy ({strategy_id}) as User B...")
    resp = requests.get(f"{BASE_URL}/strategy/{strategy_id}", headers=headers_b)
    assert resp.status_code == 404
    print("SUCCESS: User B cannot access User A's strategy directly.")

    # 8. List Strategies as A
    print("Checking User A's strategy list (should have 1)...")
    resp = requests.get(f"{BASE_URL}/strategy", headers=headers_a)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
    print("SUCCESS: User A can see their own strategy.")

if __name__ == "__main__":
    try:
        test_isolation()
        print("\nALL ISOLATION TESTS PASSED!")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
