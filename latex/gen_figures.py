"""
Generate all figures for Chapter 4 using the `diagrams` library.
Run: python gen_figures.py

KEY RULE: Edge() cannot be used inline in >> chains.
Use: e = Edge(label="x"); a >> e >> b
"""

import os

os.environ["PATH"] += os.pathsep + r"C:\Program Files\Graphviz\bin"

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Hinhve")
os.makedirs(OUT_DIR, exist_ok=True)

from diagrams import Diagram, Edge, Cluster
from diagrams.onprem.client import User
from diagrams.onprem.database import PostgreSQL
from diagrams.onprem.workflow import Airflow
from diagrams.programming.language import Python, Java
from diagrams.generic.blank import Blank
from diagrams.generic.database import SQL
from diagrams.onprem.compute import Server
from diagrams.onprem.inmemory import Redis


# ---------------------------------------------------------------
# Hinh4_1: Kiến trúc tổng thể
# ---------------------------------------------------------------
def fig_4_1():
    filename = os.path.join(OUT_DIR, "Hinh4_1_kien_truc_tong_the_multitenant_rag")
    with Diagram(
        "",
        filename=filename, outformat="png", show=False, direction="TB",
        graph_attr={"label": "Kiến trúc tổng thể Multi-tenant RAG Chatbot", "labelloc": "t", "fontsize": "16"},
    ):
        web = User("Web Chat &\nAdmin UI")
        msgr = User("Messenger")
        tg = User("Telegram")

        backend = Java("Spring Boot\nBackend")
        db = PostgreSQL("PostgreSQL")
        kb = SQL("KB Artifact\nStorage")

        runtime = Python("FastAPI\nChatbot Runtime")
        claude = Blank("Claude API\n(Anthropic)")

        web >> Edge(label="HTTP API") >> backend
        msgr >> Edge(label="Webhook") >> backend
        tg >> Edge(label="Webhook") >> backend

        e1 = Edge(label="Đọc/ghi dữ liệu")
        e2 = Edge(label="Quản lý artifact")
        e3 = Edge(label="Yêu cầu chat")
        e4 = Edge(label="Gọi API")
        backend >> e1 >> db
        backend >> e2 >> kb
        backend >> e3 >> runtime
        runtime >> e4 >> claude


# ---------------------------------------------------------------
# Hinh4_2: Offline Product Dataset & KB Artifact
# ---------------------------------------------------------------
def fig_4_2():
    filename = os.path.join(OUT_DIR, "Hinh4_2_offline_product_dataset_kb_artifact")
    with Diagram(
        "",
        filename=filename, outformat="png", show=False, direction="LR",
        graph_attr={"label": "Luồng offline xây dựng Product Dataset và KB Artifact", "labelloc": "t", "fontsize": "16"},
    ):
        source = Server("URL /\nSitemap")
        materialize = Python("Crawl &\nMaterialize")
        quality = Airflow("Quality\nGate")
        dataset = SQL("Product\nDataset")
        build = Python("Build KB")
        artifact = SQL("KB\nArtifact")

        source >> materialize >> quality

        e1 = Edge(label="Kiểm tra chất lượng")
        e2 = Edge(label="Build")
        e3 = Edge(label="Fail / Warn")
        quality >> e1 >> dataset
        dataset >> e2 >> build >> artifact
        quality >> e3 >> dataset


# ---------------------------------------------------------------
# Hinh4_3: Bind/Unbind KB với tenant
# ---------------------------------------------------------------
def fig_4_3():
    filename = os.path.join(OUT_DIR, "Hinh4_3_bind_unbind_kb_tenant")
    with Diagram(
        "",
        filename=filename, outformat="png", show=False, direction="LR",
        graph_attr={"label": "Luồng bind/unbind KB Artifact với tenant", "labelloc": "t", "fontsize": "16"},
    ):
        admin = User("Platform\nAdmin")
        bind = Java("Bind / Unbind\nService")
        binding = SQL("TenantKb\nBinding")
        version = SQL("TenantKb\nVersion")
        runtime = Python("Chatbot\nRuntime")

        admin >> Edge(label="Bind/Unbind") >> bind
        bind >> Edge(label="Tạo/cập nhật") >> binding
        bind >> Edge(label="Tạo version") >> version
        binding >> Edge(label="Trỏ tới") >> version
        bind >> Edge(label="Evict runtime") >> runtime
        version >> Edge(label="KB dir") >> runtime


# ---------------------------------------------------------------
# Hinh4_4: Online Tenant Sales RAG
# ---------------------------------------------------------------
def fig_4_4():
    filename = os.path.join(OUT_DIR, "Hinh4_4_online_tenant_sales_rag")
    with Diagram(
        "",
        filename=filename, outformat="png", show=False, direction="LR",
        graph_attr={"label": "Luồng online RAG cho chế độ tenant_sales", "labelloc": "t", "fontsize": "16"},
    ):
        user = User("Người dùng\nWeb / Messenger\n/ Telegram")

        resolve = Java("Backend:\nXác định tenant,\nconversation")
        kb_resolve = Java("Backend:\nResolve active\nKB version")
        business = Java("Backend:\nGhi hội thoại,\nkiểm tra NV")
        db = PostgreSQL("PostgreSQL\n(Message, Lead,\nPurchase Req.)")

        runtime = Python("FastAPI:\nRetrieval +\nPrompt Building")
        claude = Blank("Claude API\n(Anthropic)")
        active = SQL("Active KB\nVersion")

        user >> Edge(label="Tin nhắn") >> resolve >> kb_resolve
        kb_resolve >> Edge(label="Yêu cầu chat") >> runtime
        runtime >> Edge(label="Prompt") >> claude
        claude >> Edge(label="Phản hồi") >> runtime
        runtime >> Edge(label="Kết quả") >> business
        business >> db
        business >> Edge(label="Phản hồi") >> user
        kb_resolve << Edge(label="KB dir") << active


# ---------------------------------------------------------------
# Hinh4_5: Runtime lifecycle
# ---------------------------------------------------------------
def fig_4_5():
    filename = os.path.join(OUT_DIR, "Hinh4_5_runtime_lifecycle_active_version")
    with Diagram(
        "",
        filename=filename, outformat="png", show=False, direction="TB",
        graph_attr={"label": "Vòng đời runtime chatbot theo tenant sau publish KB", "labelloc": "t", "fontsize": "16"},
    ):
        publish = Airflow("Publish KB\nVersion")
        update = Java("Cập nhật\nactiveKbVersionId")
        evict = Java("Evict\nRuntime")
        runtime = Python("Chatbot\nRuntime")
        monitor = SQL("Runtime\nStatus")

        publish >> Edge(label="1") >> update
        update >> Edge(label="2") >> evict
        evict >> Edge(label="3") >> runtime
        runtime >> Edge(label="4. Sync") >> monitor
        update >> Edge(label="5. desired") >> monitor

        chat = User("Chat\nRequest")
        chat >> Edge(label="6. Spawn") >> runtime


# ---------------------------------------------------------------
# Hinh4_6: Ba chế độ hội thoại
# ---------------------------------------------------------------
def fig_4_6():
    filename = os.path.join(OUT_DIR, "Hinh4_6_kiem_soat_ba_mode_hoi_thoai")
    with Diagram(
        "",
        filename=filename, outformat="png", show=False, direction="TB",
        graph_attr={"label": "Kiểm soát ba chế độ hội thoại", "labelloc": "t", "fontsize": "16"},
    ):
        msg = User("Tin nhắn từ\nngười dùng")

        with Cluster("Chế độ hội thoại"):
            sales = Java("tenant_sales\nBán hàng theo\ncửa hàng")
            compare = Java("general_compare\nTư vấn chung\n/ so sánh")
            price = Java("market_price\nTham khảo giá\nthị trường")

        with Cluster("Nguồn dữ liệu"):
            kb = SQL("Tenant-bound KB\n/ Active Version")
            general = SQL("General Corpus")
            market = SQL("Dữ liệu quan\nsát / có cấu\ntrúc")

        with Cluster("Tác động nghiệp vụ"):
            lead = SQL("Lead / Purchase\nRequest")
            none1 = Blank("Không tạo")
            none2 = Blank("Không tạo")

        msg >> sales >> kb >> lead
        msg >> compare >> general >> none1
        msg >> price >> market >> none2


# ---------------------------------------------------------------
# Hinh4_7: Cross-channel identity
# ---------------------------------------------------------------
def fig_4_7():
    filename = os.path.join(OUT_DIR, "Hinh4_7_cross_channel_identity")
    with Diagram(
        "",
        filename=filename, outformat="png", show=False, direction="TB",
        graph_attr={"label": "Nhận diện khách hàng liên kênh", "labelloc": "t", "fontsize": "16"},
    ):
        web = User("Web Chat\nsession_id")
        msgr = User("Messenger\npageId +\nsenderId")
        tg = User("Telegram\nchatId /\nuserId")

        service = Java("CustomerIdentity\nService")

        with Cluster("Cơ sở dữ liệu"):
            identity = SQL("customer_identities")
            unified = SQL("unified_customers")
            conv = SQL("conversations")

        web >> Edge(label="Tìm/ tạo") >> service
        msgr >> Edge(label="Tìm/ tạo") >> service
        tg >> Edge(label="Tìm/ tạo") >> service

        service >> Edge(label="Ghi identity") >> identity
        service >> Edge(label="Merge nếu có\nphone/email") >> unified
        unified >> Edge(label="Liên kết hội\nthoại") >> conv


# ===============================================================
if __name__ == "__main__":
    print("Generating Hinh4_1..."); fig_4_1()
    print("Generating Hinh4_2..."); fig_4_2()
    print("Generating Hinh4_3..."); fig_4_3()
    print("Generating Hinh4_4..."); fig_4_4()
    print("Generating Hinh4_5..."); fig_4_5()
    print("Generating Hinh4_6..."); fig_4_6()
    print("Generating Hinh4_7..."); fig_4_7()
    print("Done! All figures saved to:", OUT_DIR)
