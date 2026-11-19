"""Gera tráfego contínuo na API: navegação, produtos inexistentes e checkouts."""
import random, time
import httpx

c = httpx.Client(base_url="http://app:8000", timeout=30)
time.sleep(5)
while True:
    try:
        r = random.random()
        if r < 0.6:
            c.get("/produtos")
        elif r < 0.85:
            c.get(f"/produtos/{random.randint(1, 6)}")
        else:
            c.post("/checkout")
    except httpx.HTTPError as e:
        print("erro:", e)
    time.sleep(random.uniform(0.05, 0.3))
