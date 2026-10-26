import os
os.environ['LLM_TIMEOUT_SECONDS'] = '10'
from bordereaux.ai.service import LLMService
from bordereaux.config import get_settings

s = get_settings()
print('before call')
result = LLMService(settings=s).answer(
    'Return a tiny JSON verdict for this reinsurance context.',
    {'scenario': 'single row mapping', 'source_column': 'UMR', 'target_field': 'umr', 'confidence': 0.98},
)
print(result)
