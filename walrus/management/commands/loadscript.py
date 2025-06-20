import importlib.util
import os
import re
import sys

from django.core.management.base import BaseCommand

SCRIPT_ROOT = 'scripts'


class Command(BaseCommand):
    help = 'Run one or more scripts from scripts/<app_name>/'

    def add_arguments(self, parser):
        parser.add_argument(
            'app_name', type=str, help='The app folder name under scripts/'
        )
        parser.add_argument(
            'script_number',
            nargs='?',
            type=str,
            help='The 4-digit script number (e.g., 0001)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List scripts to be run without executing them',
        )

    def handle(self, *args, **options):
        app_name = options['app_name']
        script_number = options.get('script_number')
        dry_run = options['dry_run']

        app_script_dir = os.path.join(SCRIPT_ROOT, app_name)
        if not os.path.isdir(app_script_dir):
            self.stderr.write(
                self.style.ERROR(f"❌ App scripts folder not found: scripts/{app_name}/")
            )
            return

        if script_number:
            if not re.match(r'^\d{4}$', script_number):
                self.stderr.write(self.style.ERROR('❌ script_number 必須是 4 位數字，例如 0001'))
                return

            matched_files = [
                f
                for f in os.listdir(app_script_dir)
                if f.startswith(script_number) and f.endswith('.py')
            ]
        else:
            matched_files = sorted(
                [
                    f
                    for f in os.listdir(app_script_dir)
                    if re.match(r'^\d{4}_.*\.py$', f)
                ]
            )
            if not dry_run:
                confirm = input(
                    f"⚠️ 你將執行 {len(matched_files)} 個 script，確定要繼續？(y/N): "
                ).lower()
                if confirm != 'y':
                    self.stdout.write(self.style.WARNING('❎ 操作已取消'))
                    return

        if not matched_files:
            self.stderr.write(self.style.ERROR('❌ 找不到符合條件的 script。'))
            return

        self.stdout.write(self.style.SUCCESS(f"✅ Scripts to run:"))
        for fname in matched_files:
            self.stdout.write(f"  - {fname}")

        if dry_run:
            self.stdout.write(self.style.WARNING('🟡 Dry-run 模式啟用，不會執行 script。'))
            return

        for script_file in matched_files:
            script_path = os.path.join(app_script_dir, script_file)
            try:
                self.stdout.write(self.style.NOTICE(f"\n▶️ 執行 {script_file}..."))

                spec = importlib.util.spec_from_file_location(
                    'script_module', script_path
                )
                module = importlib.util.module_from_spec(spec)
                sys.modules['script_module'] = module
                spec.loader.exec_module(module)

                script_class = getattr(module, 'CustomScript')
                script_instance = script_class()
                script_instance.execute()

                self.stdout.write(self.style.SUCCESS(f"✅ {script_file} 執行完成"))
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"❌ 執行 {script_file} 發生錯誤: {str(e)}")
                )
                raise e
