"""Step 1 - Golden dataset: a handful of hand-curated questions with the answer a travel expert expects.

The answers are short key facts rather than a full reply, so a correctness judge can check what matters (what was
booked, for whom, when, and where) without penalizing a different but equally good itinerary.
"""

import argparse

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
            "and the Louvre, and the reply lists the confirmation codes and the total cost."
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
            "reply lists the confirmation codes and the total cost."
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
            "and the reply lists the confirmation codes and the total cost."
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
            "Museum and a West End show, and the reply lists the confirmation codes and the total cost."
        },
    },
    {
        "inputs": {
            "question": "I'm thinking about a trip from SEA to Paris, November 12 - 16, for one person. Show me some "
            "flight and hotel options with prices, but don't book anything yet."
        },
        "outputs": {
            "answer": "Nothing is booked. The reply shows a few flight and hotel options for SEA to Paris (Nov 12 - "
            "16, 1 traveler) with prices, recommends a combination with an estimated total, and asks the user to "
            "choose before booking."
        },
    },
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recreate", action="store_true", help="Delete and recreate the dataset")
    args = parser.parse_args()

    load_dotenv(override=True)
    client = Client()

    if client.has_dataset(dataset_name=DATASET_NAME):
        if not args.recreate:
            print(f"Dataset {DATASET_NAME!r} already exists; pass --recreate to rebuild it.")
            return
        client.delete_dataset(dataset_name=DATASET_NAME)

    dataset = client.create_dataset(DATASET_NAME, description="Hand-curated travel requests with expected answers.")
    client.create_examples(dataset_id=dataset.id, examples=EXAMPLES)
    print(f"Created {len(EXAMPLES)} examples in {DATASET_NAME!r}: {dataset.url}")


if __name__ == "__main__":
    main()
