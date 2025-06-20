from abc import ABC, abstractmethod

from django.db import transaction


class BaseScript(ABC):
    @abstractmethod
    def run(self):
        raise NotImplementedError

    def execute(self):
        with transaction.atomic():
            try:
                print(f"🚀 Running {self.__class__.__name__}...")
                self.run()
                print('✅ Script finished successfully.')
            except Exception as e:
                print('❌ Error occurred during script execution.')
                raise e
