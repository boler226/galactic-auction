"""Step load profile: every 60 s add more users (use together with locustfile)."""

from locust import LoadTestShape


class StepShape(LoadTestShape):
    step_seconds = 60
    step_users = [10, 25, 50, 100, 150, 200]
    spawn_rate = 10

    def tick(self):
        step = int(self.get_run_time() // self.step_seconds)
        if step >= len(self.step_users):
            return None
        return self.step_users[step], self.spawn_rate
