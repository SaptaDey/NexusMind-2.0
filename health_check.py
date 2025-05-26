"""
Simple health check script for the NexusMind server.
"""
import requests


def check_health():
    """
    Checks the health of the NexusMind server by sending a GET request to its health endpoint.
    
    Returns:
        True if the server responds with status code 200, indicating it is healthy; False otherwise or if a connection error occurs.
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
