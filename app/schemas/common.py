from decimal import Decimal
from typing import Annotated

from pydantic import Field

# Money amount: positive, up to 16 integer digits and 2 decimals.
Money = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)]
