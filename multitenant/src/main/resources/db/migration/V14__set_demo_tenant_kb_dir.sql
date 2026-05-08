update tenants
set kb_dir = '/opt/app/chatbot/kb/article'
where code = 'demo_tenant'
  and (kb_dir is null or btrim(kb_dir) = '');
