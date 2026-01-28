"""
Wally's Cafe Jazz Club recurring event generator.

Wally's Cafe is a legendary Boston jazz club with live music every day.
This generator creates events for their regular schedule:
- Wed-Sat 7pm: Early sets (straight-ahead jazz, improvised music)
- Wed-Sun 10pm: Late night sets (jazz, soul, latin jazz, improvised music)
- Tuesday 8pm: Night band (jam session, spontaneous collaboration)
"""

from typing import List, Dict, Any

from .recurring_events import RecurringEventGenerator


class WallysCafeGenerator(RecurringEventGenerator):
    """Generator for Wally's Cafe Jazz Club recurring events."""

    @property
    def source_name(self) -> str:
        return "recurring:wallys_cafe"

    @property
    def schedule(self) -> List[Dict[str, Any]]:
        return [
            # Wed-Sat 7pm: Early sets
            {
                'days': ['wednesday', 'thursday', 'friday', 'saturday'],
                'time': '7pm',
                'bands': ["Jazz / Jam / Improv Set"],
                'genre_tags': ['jazz', 'straight-ahead jazz', 'improvised'],
            },
            # Wed-Sun 10pm: Late night sets
            {
                'days': ['wednesday', 'thursday', 'friday', 'saturday', 'sunday'],
                'time': '10pm',
                'bands': ["Late Night Set (Rotating Bands)"],
                'genre_tags': ['jazz', 'soul', 'latin jazz', 'improvised'],
            },
            # Tuesday 8pm: Night band (jam session)
            {
                'days': ['tuesday'],
                'time': '8pm',
                'bands': ["Wally's Night Band"],
                'genre_tags': ['jazz', 'improvised', 'jam session'],
            },
        ]

    def get_venue_info(self) -> Dict[str, str]:
        return {
            'id': 'wallys',
            'name': "Wally's Cafe Jazz Club",
            'location': 'Boston',
        }
