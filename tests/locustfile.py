from locust import HttpUser, task, between
class DashboardUser(HttpUser):
    wait_time = between(1, 5)
    @task
    def dashboard(self):
        self.client.get("/api/dashboard/NIFTY")
class PredictionUser(HttpUser):
    wait_time = between(2, 6)
    @task
    def predict(self):
        self.client.get("/api/quant-mtf/NIFTY")
