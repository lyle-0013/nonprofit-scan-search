from nonprofit_archive.archive_workflow import choose_answer


def test_strongest_campaign_report_drives_the_next_action() -> None:
    matches = [
        {
            "score": 0.71,
            "metadata": {
                "document_id": "receipt-18",
                "document_type": "donor_receipt",
                "text": "Donation received from Maya Chen.",
            },
        },
        {
            "score": 0.94,
            "metadata": {
                "document_id": "campaign-spring",
                "document_type": "campaign_report",
                "text": "The spring garden campaign funded 42 new plots.",
            },
        },
    ]

    answer = choose_answer(matches)

    assert answer is not None
    assert answer.document_id == "campaign-spring"
    assert answer.answer == "The spring garden campaign funded 42 new plots."
    assert answer.recommended_action == "review_campaign_results"
