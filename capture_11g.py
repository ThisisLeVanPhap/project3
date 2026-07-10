import os, sys
from unittest.mock import patch
from types import SimpleNamespace
os.environ['CHATBOT_TEST_MODE'] = '1'
sys.path.insert(0, 'chatbot')
from fastapi.testclient import TestClient
import app.server as server_module
from app.retrievers import RetrievalResult

prev_kb = server_module.KB
prev_by_mode = dict(server_module.KB_BY_MODE)
try:
    def _hit(sku, name, price, category='Den'):
        return RetrievalResult(doc_id=sku.lower().replace('-',''), chunk_id=sku.lower().replace('-','')+'#0', title=name, text=name+' la san pham noi that.', source='https://example.test/'+sku.lower(), score=10.0, metadata={'doc_type':'product','product_name':name,'category':category,'price':price,'currency':'VND','sku':sku,'source_url':'https://example.test/'+sku.lower()})
    gho262 = _hit('GHO-262', 'Den chum GHO-262', 2800000)
    gho237 = _hit('GHO-237', 'Den treo tuong GHO-237', 400000)
    tranh = _hit('TRANH-001', 'Tranh canvas', 500000, category='Tranh')
    server_module.KB = SimpleNamespace(search=lambda q,k=4,tenant_id=None: [gho262,gho237,tranh])
    server_module.KB_BY_MODE.clear()
    server_module.KB_BY_MODE['keyword'] = server_module.KB
    mock_intents = [
        {'intent':'consultation','slot_updates':{'product_category':'Den'},'slots_to_keep':[],'slots_to_clear':[],'missing_slots':['room'],'should_retrieve':False,'should_ask':True,'response_mode':'consultation_llm','confidence':0.9},
        {'intent':'update_slot','slot_updates':{'room':'phong khach'},'slots_to_keep':[],'slots_to_clear':[],'missing_slots':['budget'],'should_retrieve':False,'should_ask':True,'response_mode':'consultation_llm','confidence':0.9},
        {'intent':'add_constraint','slot_updates':{'budget':'tu 15 trieu tro xuong'},'slots_to_keep':[],'slots_to_clear':[],'missing_slots':[],'should_retrieve':True,'should_ask':False,'response_mode':'product_listing','confidence':0.9},
    ]
    intent_idx = [0]
    def mock_interpreter(*a,**k):
        i = intent_idx[0]; intent_idx[0] += 1
        return mock_intents[min(i, len(mock_intents)-1)]
    claude_calls = [0]
    def mock_claude(*a,**k):
        claude_calls[0] += 1
        return ('Minh loc duoc vai mau den phu hop cho phong khach duoi 15 trieu. GHO-262 hop neu ban muon tao diem nhan trung tam, con GHO-237 gon hon cho trang tri phu. Ban muon uu tien den chum hay den treo tuong?', None, None)
    action_idx = [0]
    def action_side(*a,**k):
        action_idx[0] += 1
        return 'ask_discovery' if action_idx[0] <= 2 else 'none'
    with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'fake'}):
        with patch('app.server._is_pytest_blocking_real_claude', return_value=False):
            with patch('app.server.call_state_interpreter', side_effect=mock_interpreter):
                with patch('app.server._sales_action_from_state', side_effect=action_side):
                    with patch('app.server._call_claude_api', side_effect=mock_claude):
                        client = TestClient(server_module.app)
                        conv = 'flow-den-pk-15tr'
                        client.post('/chat', json={'message':'t muon mua 1 cai den','history':[],'conversation_id':conv,'tenant_id':'t','channel':'web','gen':{'provider':'stub','mode':'tenant_sales','retrieval_mode':'keyword','retrieval_top_k':4,'answer_mode':'template','sales_mode':'active'}})
                        client.post('/chat', json={'message':'phong khach','history':[],'conversation_id':conv,'tenant_id':'t','channel':'web','gen':{'provider':'stub','mode':'tenant_sales','retrieval_mode':'keyword','retrieval_top_k':4,'answer_mode':'template','sales_mode':'active'}})
                        claude_calls[0] = 0
                        r3 = client.post('/chat', json={'message':'tu 15 trieu tro xuong','history':[],'conversation_id':conv,'tenant_id':'t','channel':'web','gen':{'provider':'stub','mode':'tenant_sales','retrieval_mode':'keyword','retrieval_top_k':4,'answer_mode':'template','sales_mode':'active'}})
                        p = r3.json()
                        reply = p.get('reply','')
                        print('=== FOCUSED RESULT ===')
                        print('FINAL_ANSWER_START')
                        print(reply)
                        print('FINAL_ANSWER_END')
                        print('CLAUDE_CALL_COUNT:', claude_calls[0])
                        prompt = server_module._build_tenant_sales_listing_prompt('test', [{'name':'X','sku':'Y','price':1,'url':'z'}], {})
                        print('PROMPT_HAS_KHONG_BIA_SKU:', 'KHÔNG BỊA SKU' in prompt or 'KHONG BIA SKU' in prompt)
                        print('PROMPT_HAS_KHONG_BIA_AVAIL:', 'KHÔNG BỊA tình trạng kho' in prompt or 'KHONG BIA tinh trang kho' in prompt)
finally:
    server_module.KB = prev_kb
    server_module.KB_BY_MODE.clear()
    server_module.KB_BY_MODE.update(prev_by_mode)
