"""
Simple health check script for the NexusMind server.
"""
import requests


def check_health():
    """
    Checks if the NexusMind server is healthy by querying its health endpoint.
    
    Sends an HTTP GET request to 'http://localhost:8000/health'. Returns True if the server responds with status code 200; otherwise, returns False. Handles connection errors by returning False.
    """
    try:
        response = requests.get("http://localhost:8000/health")
        if response.status_code == 200:
            print(f"Health check succeeded! Response: {response.json()}")
            return True
        else:
            print(f"Health check failed with status code {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except requests.RequestException as e:
        print(f"Connection error: {e}")
        return False

if __name__ == "__main__":
    check_health()
