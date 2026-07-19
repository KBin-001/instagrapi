from datetime import UTC, datetime, timedelta

from app.analysis.similarity import compute_local_similarity
from app.models import (
    AccountTypeClassification,
    ContactInfo,
    MediaMetrics,
    MexicoSignal,
    NicheClassification,
    ProfileData,
    SearchIntent,
)


def _profile(username: str, biography: str) -> ProfileData:
    return ProfileData(
        username=username,
        biography=biography,
        follower_count=104_000,
        collected_at=datetime.now(UTC),
    )


def test_similar_perfume_creator_prefers_matching_seed() -> None:
    candidate = _profile("aromas.mx", "Reseñas de perfumes y fragancias en CDMX")
    metrics = MediaMetrics(days_since_last_post=5, last_post_date=datetime.now(UTC) - timedelta(days=5))

    score, breakdown, seed = compute_local_similarity(
        candidate,
        brief="creadora mexicana de perfumes y belleza",
        seed_documents={
            "perfume.seed": "perfumes fragancias aromas reseñas belleza mexico",
            "fashion.seed": "moda outfits zapatos fashion",
        },
        niche=NicheClassification(primary_niche="perfume", niche_scores={"perfume": 0.9}),
        mexico=MexicoSignal(mexico_confidence_score=0.8),
        account_type=AccountTypeClassification(account_type="personal_creator"),
        metrics=metrics,
        intent=SearchIntent(
            raw_brief="creadora mexicana de perfumes y belleza",
            target_niches=["perfume"],
            target_regions=["mexico"],
            min_followers=10_000,
            max_followers=300_000,
            require_public_contact=True,
        ),
        contact=ContactInfo(has_public_contact=True),
        captions=["Mi perfume favorito en México"],
        source_count=3,
    )

    assert seed == "perfume.seed"
    assert score > 50
    assert set(breakdown) == {
        "brief_text",
        "seed_text",
        "niche",
        "region_language",
        "follower_fit",
        "engagement",
        "creator_type",
        "activity",
        "multi_source",
        "public_contact",
        "reasons",
    }
