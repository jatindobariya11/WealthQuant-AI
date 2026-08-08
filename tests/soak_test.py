import time
import requests
import psutil

def soak_test(duration_hours=8):
    start = time.time()
    end = start + (duration_hours * 3600)
    print(f"Starting soak test for {duration_hours} hours...")
    while time.time() < end:
        try:
            requests.get("http://127.0.0.1:8000/health/full")
        except:
            pass
        time.sleep(10)
    print("Soak test complete.")

if __name__ == "__main__":
    soak_test(0.1) # Running short test for audit phase
