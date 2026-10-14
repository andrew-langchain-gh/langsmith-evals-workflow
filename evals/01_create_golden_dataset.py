"""Step 1 - Golden dataset: a handful of hand-curated questions with the answer a travel expert expects.

The answers are short key facts rather than a full reply, so a correctness judge can check what matters (what was
booked, for whom, when, and where) without penalizing a different but equally good itinerary.
Named assertions capture individual acceptance criteria for an assertion-aware offline evaluator.
"""

import argparse
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client

from travel_planner.evals.settings import DATASET_NAME

EXAMPLES = [
    {
        "inputs": {
            "question": "Book a 5 night trip to Paris from October 5 - 10 staying at the Loft Montmartre Hotel for 2 "
            "travelers. I have a high budget and I fly out of SFO. Plan an itinerary that includes the Eiffel Tower, "
            "Versailles, and the Louvre. My name is Jack Spade."
        },
        "outputs": {
            "answer": "Booked round-trip flights SFO to Paris (out Oct 5, back Oct 10) for 2 travelers under Jack "
            "Spade, and 5 nights at the Loft Montmartre Hotel. The itinerary includes the Eiffel Tower, Versailles, "
            "and the Louvre, and the reply lists the confirmation codes and the total cost.",
            "assertions": [
                {"key": "must_match_trip_details", "comment": "The response describes round-trip flights from SFO "
                 "to Paris, departing October 5 and returning October 10, for two travelers under Jack Spade."},
                {"key": "must_match_hotel", "comment": "The response describes a five-night booking at the Loft "
                 "Montmartre Hotel, checking in October 5 and checking out October 10."},
                {"key": "must_include_requested_activities", "comment": "The itinerary includes the Eiffel Tower, "
                 "Versailles, and the Louvre."},
                {"key": "must_report_confirmation_codes", "comment": "The response lists confirmation codes for "
                 "the outbound flight, return flight, and hotel booking."},
                {"key": "must_report_total_cost", "comment": "The response states the total cost of the booked "
                 "flights and hotel, including the currency."},
            ],
        },
    },
    {
        "inputs": {
            "question": "Book me a trip from LAX to Tokyo, November 10 - 14, staying at the Boutique Shinjuku Inn. "
            "It's just me and I have a mid-range budget. I love food and museums. My name is Priya Shah."
        },
        "outputs": {
            "answer": "Booked round-trip flights LAX to Tokyo (out Nov 10, back Nov 14) for 1 traveler under Priya "
            "Shah, and 4 nights at the Boutique Shinjuku Inn. The itinerary focuses on food and museums, and the "
            "reply lists the confirmation codes and the total cost.",
            "assertions": [
                {"key": "must_match_trip_details", "comment": "The response describes round-trip flights from LAX "
                 "to Tokyo, departing November 10 and returning November 14, for one traveler under Priya Shah."},
                {"key": "must_match_hotel", "comment": "The response describes a four-night booking at the "
                 "Boutique Shinjuku Inn, checking in November 10 and checking out November 14."},
                {"key": "must_include_requested_activities", "comment": "The itinerary includes food experiences "
                 "and museum visits in Tokyo."},
                {"key": "must_report_confirmation_codes", "comment": "The response lists confirmation codes for "
                 "the outbound flight, return flight, and hotel booking."},
                {"key": "must_report_total_cost", "comment": "The response states the total cost of the booked "
                 "flights and hotel, including the currency."},
            ],
        },
    },
    {
        "inputs": {
            "question": "Book a week in Rome for 2 people, November 2 - 9, flying from JFK. Put us at the Royal "
            "Trastevere Hotel. We want to see the Colosseum and the Vatican. The booking name is Morgan Diaz."
        },
        "outputs": {
            "answer": "Booked round-trip flights JFK to Rome (out Nov 2, back Nov 9) for 2 travelers under Morgan "
            "Diaz, and 7 nights at the Royal Trastevere Hotel. The itinerary includes the Colosseum and the Vatican, "
            "and the reply lists the confirmation codes and the total cost.",
            "assertions": [
                {"key": "must_match_trip_details", "comment": "The response describes round-trip flights from JFK "
                 "to Rome, departing November 2 and returning November 9, for two travelers under Morgan Diaz."},
                {"key": "must_match_hotel", "comment": "The response describes a seven-night booking at the Royal "
                 "Trastevere Hotel, checking in November 2 and checking out November 9."},
                {"key": "must_include_requested_activities", "comment": "The itinerary includes the Colosseum "
                 "and the Vatican."},
                {"key": "must_report_confirmation_codes", "comment": "The response lists confirmation codes for "
                 "the outbound flight, return flight, and hotel booking."},
                {"key": "must_report_total_cost", "comment": "The response states the total cost of the booked "
                 "flights and hotel, including the currency."},
            ],
        },
    },
    {
        "inputs": {
            "question": "Book me a trip from SFO to London, December 7 - 11, at the Park Soho Suites. I'm traveling "
            "alone on a tight budget and want to see the British Museum and a West End show. I'm Alex Rivera."
        },
        "outputs": {
            "answer": "Booked the cheapest sensible round-trip flights SFO to London (out Dec 7, back Dec 11) for 1 "
            "traveler under Alex Rivera, and 4 nights at the Park Soho Suites. The itinerary includes the British "
            "Museum and a West End show, and the reply lists the confirmation codes and the total cost.",
            "assertions": [
                {"key": "must_match_trip_details", "comment": "The response describes round-trip flights from SFO "
                 "to London, departing December 7 and returning December 11, for one traveler under Alex Rivera."},
                {"key": "must_match_hotel", "comment": "The response describes a four-night booking at the Park "
                 "Soho Suites, checking in December 7 and checking out December 11."},
                {"key": "must_include_requested_activities", "comment": "The itinerary includes the British "
                 "Museum and a West End show."},
                {"key": "must_report_confirmation_codes", "comment": "The response lists confirmation codes for "
                 "the outbound flight, return flight, and hotel booking."},
                {"key": "must_report_total_cost", "comment": "The response states the total cost of the booked "
                 "flights and hotel, including the currency."},
            ],
        },
    },
    {
        "inputs": {
            "question": "Book me a trip from SEA to Paris, November 12 - 16, staying at the Loft Montmartre Hotel. "
            "I'm traveling alone with a mid-range budget and want to see the Eiffel Tower and the Louvre. "
            "My name is Jamie Chen."
        },
        "outputs": {
            "answer": "Booked round-trip flights SEA to Paris (out Nov 12, back Nov 16) for 1 traveler under Jamie "
            "Chen, and 4 nights at the Loft Montmartre Hotel. The itinerary includes the Eiffel Tower and the "
            "Louvre, and the reply lists the confirmation codes and the total cost.",
            "assertions": [
                {"key": "must_match_trip_details", "comment": "The response describes round-trip flights from SEA "
                 "to Paris, departing November 12 and returning November 16, for one traveler under Jamie Chen."},
                {"key": "must_match_hotel", "comment": "The response describes a four-night booking at the Loft "
                 "Montmartre Hotel, checking in November 12 and checking out November 16."},
                {"key": "must_include_requested_activities", "comment": "The itinerary includes the Eiffel Tower "
                 "and the Louvre."},
                {"key": "must_report_confirmation_codes", "comment": "The response lists confirmation codes for "
                 "the outbound flight, return flight, and hotel booking."},
                {"key": "must_report_total_cost", "comment": "The response states the total cost of the booked "
                 "flights and hotel, including the currency."},
            ],
        },
    },
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recreate", action="store_true", help="Delete and recreate the dataset")
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    client = Client()

    if client.has_dataset(dataset_name=DATASET_NAME):
        if not args.recreate:
            print(f"Dataset {DATASET_NAME!r} already exists; pass --recreate to rebuild it.")
            return
        client.delete_dataset(dataset_name=DATASET_NAME)

    dataset = client.create_dataset(
        DATASET_NAME, description="Hand-curated travel requests with expected answers and named acceptance assertions."
    )
    client.create_examples(dataset_id=dataset.id, examples=EXAMPLES)
    print(f"Created {len(EXAMPLES)} examples in {DATASET_NAME!r}: {dataset.url}")


if __name__ == "__main__":
    main()
