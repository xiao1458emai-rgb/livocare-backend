# main/services/fda_service.py
import requests
import time
from django.conf import settings
from ..models import Medication

class FDAService:
    """خدمة جلب بيانات الأدوية من openFDA"""
    
    BASE_URL = "https://api.fda.gov/drug"
    
    def __init__(self):
        self.api_key = getattr(settings, 'gizfuqNrpFAXGPuuIDASFr60npNE4ONvspiq4kl9', None)
    
    def _make_request(self, endpoint, params=None):
        """تنفيذ طلب إلى openFDA"""
        if params is None:
            params = {}
        
        if self.api_key:
            params['api_key'] = self.api_key
        
        url = f"{self.BASE_URL}/{endpoint}.json"
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching from openFDA: {e}")
            return None
    
    def search_by_brand_name(self, brand_name, limit=10):
        """البحث عن دواء بالاسم التجاري"""
        params = {
            'search': f'openfda.brand_name.exact:"{brand_name}"',
            'limit': limit
        }
        data = self._make_request('drugsfda', params)
        
        if data and 'results' in data:
            return self._parse_drug_results(data['results'])
        return []
    
    def search_by_generic_name(self, generic_name, limit=10):
        """البحث عن دواء بالاسم العلمي"""
        params = {
            'search': f'openfda.generic_name:"{generic_name}"',
            'limit': limit
        }
        data = self._make_request('drugsfda', params)
        
        if data and 'results' in data:
            return self._parse_drug_results(data['results'])
        return []
    
    def search_by_ndc(self, ndc_code):
        """البحث عن دواء بـ NDC"""
        params = {
            'search': f'openfda.product_ndc:"{ndc_code}"',
            'limit': 1
        }
        data = self._make_request('drugsfda', params)
        
        if data and 'results' and len(data['results']) > 0:
            return self._parse_drug(data['results'][0])
        return None
    
    def get_drug_label(self, drug_name, search_field='openfda.brand_name'):
        """الحصول على معلومات السلامة للدواء"""
        params = {
            'search': f'{search_field}:"{drug_name}"',
            'limit': 1
        }
        data = self._make_request('label', params)
        
        if data and 'results' and len(data['results']) > 0:
            return self._parse_label(data['results'][0])
        return None
    
    def _parse_drug_results(self, results):
        """تحويل نتائج الأدوية إلى قائمة"""
        parsed = []
        for result in results:
            parsed.append(self._parse_drug(result))
        return parsed
    
    def _parse_drug(self, drug_data):
        """تحويل بيانات دواء فردية"""
        openfda = drug_data.get('openfda', {})
        products = drug_data.get('products', [])
        
        return {
            'brand_name': openfda.get('brand_name', [''])[0] if openfda.get('brand_name') else '',
            'generic_name': openfda.get('generic_name', [''])[0] if openfda.get('generic_name') else '',
            'manufacturer': openfda.get('manufacturer_name', [''])[0] if openfda.get('manufacturer_name') else '',
            'ndc_code': openfda.get('product_ndc', [''])[0] if openfda.get('product_ndc') else '',
            'dosage_form': products[0].get('dosage_form', '') if products else '',
            'route': products[0].get('route', '') if products else '',
            'strength': products[0].get('strength', '') if products else '',
        }
    
    def _parse_label(self, label_data):
        """تحويل بيانات السلامة للدواء"""
        return {
            'indications': label_data.get('indications_and_usage', [''])[0] if label_data.get('indications_and_usage') else '',
            'warnings': label_data.get('warnings', [''])[0] if label_data.get('warnings') else '',
            'contraindications': label_data.get('contraindications', [''])[0] if label_data.get('contraindications') else '',
            'adverse_reactions': label_data.get('adverse_reactions', [''])[0] if label_data.get('adverse_reactions') else '',
            'dosage_administration': label_data.get('dosage_and_administration', [''])[0] if label_data.get('dosage_and_administration') else '',
        }
    
    def import_drug_to_database(self, drug_data):
        """استيراد دواء إلى قاعدة البيانات"""
        medication, created = Medication.objects.get_or_create(
            ndc_code=drug_data.get('ndc_code', ''),
            defaults={
                'brand_name': drug_data.get('brand_name', ''),
                'generic_name': drug_data.get('generic_name', ''),
                'manufacturer': drug_data.get('manufacturer', ''),
                'dosage_form': drug_data.get('dosage_form', ''),
                'route': drug_data.get('route', ''),
                'strength': drug_data.get('strength', ''),
            }
        )
        
        # إذا كان موجوداً بالفعل، قم بتحديثه
        if not created:
            medication.brand_name = drug_data.get('brand_name', medication.brand_name)
            medication.generic_name = drug_data.get('generic_name', medication.generic_name)
            medication.manufacturer = drug_data.get('manufacturer', medication.manufacturer)
            medication.dosage_form = drug_data.get('dosage_form', medication.dosage_form)
            medication.route = drug_data.get('route', medication.route)
            medication.strength = drug_data.get('strength', medication.strength)
            medication.save()
        
        return medication