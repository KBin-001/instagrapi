from datetime import UTC, datetime, timedelta

from app.config import build_settings
from app.extension.models import (
    ExtensionCandidateItem,
    ExtensionMediaPayload,
    ExtensionProfileData,
    ExtensionTaskCreate,
    QueueFailurePayload,
    TaskCandidatesPayload,
    TaskProfilePayload,
    TaskRerankPayload,
)
from app.extension.task_service import ExtensionTaskService, normalize_username
from app.storage.database import Database
from app.storage.repositories import load_all_records


def _service(tmp_path) -> ExtensionTaskService:
    settings = build_settings(
        cli_overrides={
            "checkpoint": {"database_file": str(tmp_path / "task.db")},
            "filters": {"require_mexico_signal": False},
        }
    )
    return ExtensionTaskService(settings=settings)


def test_normalize_username_handles_urls_case_and_invalid_media() -> None:
    assert normalize_username("HTTPS://INSTAGRAM.COM/Creator.Name/") == "creator.name"
    assert normalize_username("@Creator_Name") == "creator_name"
    assert normalize_username("https://instagram.com/reel/ABC123/") is None


def test_queue_is_ordered_deduplicated_and_controllable(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.create_task(
        ExtensionTaskCreate(
            seeds=["Creator.One", "https://instagram.com/creator.one/"],
            hashtags=["PerfumeMexico"],
        )
    )
    task_id = result["task_id"]
    assert result["queue"] == {"pending": 2}

    first = service.next_item(task_id)
    assert first["item"]["page_type"] == "profile"
    service.control(task_id, "pause")
    assert service.next_item(task_id)["item"] is None
    service.control(task_id, "resume")
    reclaimed = service.next_item(task_id)["item"]
    assert reclaimed["id"] == first["item"]["id"]
    assert reclaimed["attempt_count"] == 2
    now = datetime.now(UTC)
    service.submit_profile(
        task_id,
        TaskProfilePayload(
            queue_item_id=reclaimed["id"],
            collected_at=now,
            page_url=reclaimed["url"],
            profile=ExtensionProfileData(
                username="creator.one",
                follower_text="50K",
                is_private=False,
            ),
        ),
    )
    hashtag_item = service.next_item(task_id)["item"]
    assert hashtag_item["page_type"] == "hashtag"

    service.submit_candidates(
        task_id,
        TaskCandidatesPayload(
            queue_item_id=hashtag_item["id"],
            source_page_url=hashtag_item["url"],
            source_type="hashtag",
            candidates=[],
            media_urls=[
                "https://www.instagram.com/reel/ABC123/",
                "https://www.instagram.com/reel/ABC123/",
            ],
        ),
    )
    active = service.active_task()
    assert active is not None
    assert active["queue"]["completed"] == 2
    assert active["queue"]["pending"] == 1


def test_brief_only_creates_automatic_keyword_search(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.create_task(ExtensionTaskCreate(brief="寻找墨西哥香水创作者"))

    claimed = service.next_item(result["task_id"])["item"]
    assert claimed["page_type"] == "keyword"
    assert "perfume" in claimed["source_value"]
    assert "/explore/search/keyword/" in claimed["url"]


def test_seed_consumes_profile_budget_without_media_fanout(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.create_task(
        ExtensionTaskCreate(seeds=["seed.creator"], hashtags=["perfumemexico"], max_profiles_to_analyze=1)
    )
    task_id = result["task_id"]
    profile_item = service.next_item(task_id)["item"]
    service.submit_profile(
        task_id,
        TaskProfilePayload(
            queue_item_id=profile_item["id"],
            collected_at=datetime.now(UTC),
            page_url=profile_item["url"],
            profile=ExtensionProfileData(username="seed.creator", follower_text="25K", is_private=False),
        ),
    )
    assert service.next_item(task_id)["item"] is None
    assert service.active_task() is None
    events = service.events(task_id)
    assert any(event["event_type"] == "analysis_budget_reached" for event in events)


def test_completed_discovery_media_is_reused_for_profile_analysis(tmp_path) -> None:
    service = _service(tmp_path)
    task_id = service.create_task(ExtensionTaskCreate(hashtags=["perfumemexico"], max_profiles_to_analyze=3))["task_id"]
    source_item = service.next_item(task_id)["item"]
    service.submit_candidates(
        task_id,
        TaskCandidatesPayload(
            queue_item_id=source_item["id"],
            source_page_url=source_item["url"],
            source_type="hashtag",
            candidates=[],
            media_urls=["https://www.instagram.com/reel/REUSED1/"],
        ),
    )
    media_item = service.next_item(task_id)["item"]
    service.submit_media(
        task_id,
        ExtensionMediaPayload(
            queue_item_id=media_item["id"],
            username="reused.creator",
            media_url=media_item["url"],
            shortcode="REUSED1",
            caption="Perfumes en México",
            collected_at=datetime.now(UTC),
        ),
    )
    profile_item = service.next_item(task_id)["item"]
    submitted = service.submit_profile(
        task_id,
        TaskProfilePayload(
            queue_item_id=profile_item["id"],
            collected_at=datetime.now(UTC),
            page_url=profile_item["url"],
            profile=ExtensionProfileData(
                username="reused.creator",
                biography="Perfumes en México contacto@example.com",
                follower_text="25K",
                is_private=False,
            ),
            recent_media_urls=[media_item["url"]],
        ),
    )

    assert submitted["media_queued"] == 0
    review = service.next_review_creator(task_id)
    assert review["data_quality_status"] == "complete"
    assert service.active_task()["queue"].get("pending", 0) == 0


def test_seed_recommendations_are_processed_before_seed_media_and_hashtags(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.create_task(
        ExtensionTaskCreate(seeds=["seed.creator"], hashtags=["perfumemexico"], max_profiles_to_analyze=5)
    )
    task_id = result["task_id"]
    profile_item = service.next_item(task_id)["item"]
    service.submit_profile(
        task_id,
        TaskProfilePayload(
            queue_item_id=profile_item["id"],
            collected_at=datetime.now(UTC),
            page_url=profile_item["url"],
            profile=ExtensionProfileData(username="seed.creator", is_private=False),
            visible_recommendations=[ExtensionCandidateItem(username="similar.creator")],
            recent_media_urls=["https://www.instagram.com/reel/SEEDMEDIA/"],
        ),
    )

    next_item = service.next_item(task_id)["item"]
    assert next_item["page_type"] == "profile"
    assert next_item["username"] == "similar.creator"


def test_non_retryable_failure_is_logged_and_can_not_be_retried(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.create_task(ExtensionTaskCreate(seeds=["broken.creator"]))
    task_id = result["task_id"]
    item = service.next_item(task_id)["item"]

    response = service.report_failure(
        task_id,
        QueueFailurePayload(
            queue_item_id=item["id"],
            error="422 payload invalid",
            retryable=False,
            error_code="payload_validation",
            diagnostics={"has_og_title": True, "article_count": 0},
        ),
    )

    assert response["item_status"] == "failed"
    assert service.retry_failed(task_id)["retried"] == 0
    assert service.events(task_id)[0]["event_type"] == "failed_items_retried"
    assert "article_count" in service.events(task_id)[1]["message"]


def test_discovery_media_is_interleaved_and_globally_bounded(tmp_path) -> None:
    settings = build_settings(
        cli_overrides={
            "checkpoint": {"database_file": str(tmp_path / "bounded.db")},
            "discovery": {"max_discovery_media": 2, "media_per_hashtag": 20},
            "filters": {"require_mexico_signal": False},
        }
    )
    service = ExtensionTaskService(settings=settings)
    result = service.create_task(ExtensionTaskCreate(hashtags=["firsttag", "secondtag"], max_profiles_to_analyze=10))
    task_id = result["task_id"]
    first_source = service.next_item(task_id)["item"]
    assert first_source["page_type"] == "hashtag"

    submitted = service.submit_candidates(
        task_id,
        TaskCandidatesPayload(
            queue_item_id=first_source["id"],
            source_page_url=first_source["url"],
            source_type="hashtag",
            candidates=[],
            media_urls=[
                "https://www.instagram.com/reel/ONE/",
                "https://www.instagram.com/reel/TWO/",
                "https://www.instagram.com/reel/THREE/",
            ],
        ),
    )

    assert submitted["media_queued"] == 2
    next_item = service.next_item(task_id)["item"]
    assert next_item["page_type"] == "media"


def test_media_author_is_prioritized_and_visible_in_recent_candidates(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.create_task(ExtensionTaskCreate(hashtags=["perfumemexico"], max_profiles_to_analyze=10))
    task_id = result["task_id"]
    source_item = service.next_item(task_id)["item"]
    service.submit_candidates(
        task_id,
        TaskCandidatesPayload(
            queue_item_id=source_item["id"],
            source_page_url=source_item["url"],
            source_type="hashtag",
            candidates=[],
            media_urls=["https://www.instagram.com/reel/AUTHOR1/"],
        ),
    )
    media_item = service.next_item(task_id)["item"]
    service.submit_media(
        task_id,
        ExtensionMediaPayload(
            queue_item_id=media_item["id"],
            username="new.creator",
            media_url=media_item["url"],
            shortcode="AUTHOR1",
            collected_at=datetime.now(UTC),
            field_sources={"username": "meta"},
        ),
    )

    active = service.active_task()
    assert active["recent_candidates"][0]["username"] == "new.creator"
    profile_item = service.next_item(task_id)["item"]
    assert profile_item["page_type"] == "profile"
    assert profile_item["username"] == "new.creator"


def test_profile_media_analysis_and_result_status(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.create_task(
        ExtensionTaskCreate(
            seeds=["perfume.creator"],
            min_followers=20_000,
            max_followers=300_000,
            require_mexico_signal=False,
        )
    )
    task_id = result["task_id"]
    profile_item = service.next_item(task_id)["item"]
    now = datetime.now(UTC)

    service.submit_profile(
        task_id,
        TaskProfilePayload(
            queue_item_id=profile_item["id"],
            collected_at=now,
            page_url="https://www.instagram.com/perfume.creator/",
            profile=ExtensionProfileData(
                username="perfume.creator",
                full_name="Perfume Creator MX",
                biography="Perfumes y fragancias en CDMX · colaboración: hello@example.com",
                follower_text="52.4K",
                following_text="850",
                post_count_text="120",
                public_email="hello@example.com",
                is_private=False,
            ),
            recent_media_urls=["https://www.instagram.com/reel/MEDIA123/"],
        ),
    )
    media_item = service.next_item(task_id)["item"]
    assert media_item["page_type"] == "media"

    service.submit_media(
        task_id,
        ExtensionMediaPayload(
            queue_item_id=media_item["id"],
            username="perfume.creator",
            media_url=media_item["url"],
            shortcode="MEDIA123",
            media_type="reel",
            taken_at=now - timedelta(days=3),
            caption="Perfume favorito en México #perfumemexico",
            like_count=1200,
            comment_count=80,
            visible_play_count=12_000,
            is_reel=True,
            collected_at=now,
        ),
    )

    review = service.next_review_creator(task_id)
    assert review is not None
    assert review["username"] == "perfume.creator"
    assert review["public_email"] == "hello@example.com"
    service.review_creator(task_id, "perfume.creator", "save")

    db = Database(service.settings.checkpoint.database_file)
    session = db.get_session()
    try:
        records = load_all_records(session, task_id)
    finally:
        session.close()
        db.close()

    assert len(records) == 1
    record = records[0]
    assert record.metrics is not None
    assert record.metrics.median_visible_reel_views == 12_000
    assert record.contact is not None and record.contact.public_email == "hello@example.com"
    assert record.match_status == "matched"
    assert record.discovery_sources
    assert record.review_status == "saved"
    assert record.in_library is True

    duplicate_task = service.create_task(ExtensionTaskCreate(seeds=["perfume.creator"]))
    assert duplicate_task["queue"] == {}


def test_existing_candidates_can_be_reranked_from_natural_language_brief(tmp_path) -> None:
    service = _service(tmp_path)
    task_id = service.create_task(ExtensionTaskCreate(seeds=["mexico.perfume"], max_profiles_to_analyze=2))["task_id"]
    profile_item = service.next_item(task_id)["item"]
    service.submit_profile(
        task_id,
        TaskProfilePayload(
            queue_item_id=profile_item["id"],
            collected_at=datetime.now(UTC),
            page_url=profile_item["url"],
            profile=ExtensionProfileData(
                username="mexico.perfume",
                biography="Creadora de reseñas de perfumes en CDMX · contacto hola@example.com",
                follower_text="45K",
                public_email="hola@example.com",
                is_private=False,
            ),
        ),
    )

    result = service.rerank_candidates(
        task_id,
        TaskRerankPayload(
            brief="墨西哥香水个人创作者，粉丝数量大于1万，必须有公开联系方式",
        ),
    )

    assert result["profiles_reranked"] == 1
    assert result["intent"]["min_followers"] == 10_000
    assert result["top_candidates"][0]["username"] == "mexico.perfume"
    assert result["top_candidates"][0]["similarity_score"] > 50
    assert "reasons" in result["top_candidates"][0]["similarity_breakdown"]
