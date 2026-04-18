"""
Regression tests for StampAuctionNetwork dispatcher job caps.

These tests cover the private collectibles pipeline that discovers StampAuctionNetwork
sale and catalog pages, persists normalized lot rows into `sales_listings`, and
downloads lot images into local media storage when available.
"""

import os
import sys
from pathlib import Path
from typing import Any, Mapping

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from private.collectibles.jobcaps.auction_support import (  # noqa: E402
    TABLE_AUCTIONEERS,
    TABLE_AUCTIONS,
    auctioneers_table_schema,
    auctions_table_schema,
)
from private.collectibles.jobcaps.web_support import (  # noqa: E402
    TABLE_WEB_PAGES,
    web_pages_table_schema,
)
from private.collectibles.jobcaps.stamp_auction_network import (  # noqa: E402
    PRIORITY_IMAGE,
    PRIORITY_LISTING,
    PRIORITY_PAGE_NEW_AUCTION,
    PRIORITY_PAGE_SAME_AUCTION,
    TABLE_SALES_LISTINGS,
    StampAuctionNetworkImageJobCap,
    StampAuctionNetworkJobCap,
    StampAuctionNetworkListingJobCap,
    StampAuctionNetworkPageJobCap,
    sales_listings_table_schema,
)
from prompits.dispatcher.models import JobDetail  # noqa: E402
from prompits.dispatcher.runtime import build_dispatch_job  # noqa: E402
from prompits.dispatcher.schema import TABLE_JOBS, ensure_dispatcher_tables  # noqa: E402
from prompits.pools.sqlite import SQLitePool  # noqa: E402


AUCTIONS_HTML = """
<html><body>
  <a href="https://stampauctionnetwork.com/V/V5317.cfm">
    Weekly Online Sales - a Division of Daniel F. Kelleher Auctions Sale - 5317
  </a>
  <a href="https://stampauctionnetwork.com/MC/MC156.cfm">
    Encheres Champagne Auctions Sale - 156
  </a>
  <a href="https://stampauctionnetwork.com/MC/MC156.cfm?TargetAdNo=MC156&TargetAudno=FEATURE">
    Encheres Champagne Auctions Sale - 156 Feature
  </a>
</body></html>
"""


UPDATED_AUCTIONS_HTML = """
<html><body>
  <a href="https://stampauctionnetwork.com/V/V5317.cfm">
    Weekly Online Sales - a Division of Daniel F. Kelleher Auctions Sale - 5317
  </a>
  <a href="https://stampauctionnetwork.com/MC/MC156.cfm">
    Encheres Champagne Auctions Sale - 156
  </a>
  <a href="https://stampauctionnetwork.com/ZA/ZA420.cfm">
    AB Philea Online Stamp Auction - April 15-16, 2026
  </a>
</body></html>
"""


SALE_PAGE_HTML = """
<html>
  <head>
    <title>Weekly Online Sales - a Division of Daniel F. Kelleher Auctions Sale - 5317</title>
  </head>
  <body>
    <a href="https://stampauctionnetwork.com/aCatalog.cfm?SrchFirm=V&SrchSale=5317">Table of Contents</a>
    <a href="https://stampauctionnetwork.com/aCatalog3.cfm?MAJGROUP=United+States&SrchFirm=V&SrchSale=5317">United States</a>
    <a href="https://stampauctionnetwork.com/iCatalog2TOC.cfm?MAJGROUP=BANKNOTES&SrchFirm=V&SrchSale=5317">Banknotes</a>
    <a href="https://stampauctionnetwork.com/Auctions.cfm?privatechannelType=EN">English Auction Firms</a>
    <a href="https://stampauctionnetwork.com/ZA/ZA420.cfm">Unrelated sale</a>
  </body>
</html>
"""


CATALOG_PAGE_HTML = """
<html><body>
  <div>Records 1 to 2 of 3</div>
  <a href="https://stampauctionnetwork.com/aCatalog3.cfm?MAJGROUP=United+States&Page=2&SrchFirm=V&SrchSale=5317">Next</a>
  <a href="https://stampauctionnetwork.com/NZ/NZ30.cfm">Another unrelated sale</a>

  <a href="https://stampauctionnetwork.com/V/v53174.cfm#Lot5140">More Info</a>
  <img src="https://stampauctionnetwork.com/Photos/V/5317/5140.jpg" alt="Lot 5140" />
  <div>United States</div>
  <div>Air Post stamps</div>
  <div>Sale No: 5317</div>
  <div>Lot No: 5140</div>
  <div>Symbol: **</div>
  <div>Cat No: Scott #287 1898, 4c Trans-Mississippi single with imprint (Image)</div>
  <div>Opening US$ 250.00</div>
  <div>Sold...US$ 300.00</div>
  <div>Closed..Apr-12-2026, 21:00:00 EST</div>

  <a href="https://stampauctionnetwork.com/V/v53174.cfm#Lot5141">More Info</a>
  <div>United States</div>
  <div>Commemoratives</div>
  <div>Sale No: 5317</div>
  <div>Lot No: 5141</div>
  <div>Symbol: *</div>
  <div>Cat No: Scott #288 1898, 5c Trans-Mississippi</div>
  <div>Opening US$ 200.00</div>
  <div>Currently US$ 250.00</div>
</body></html>
"""


DETAIL_PAGE_HTML = """
<html>
  <head>
    <title>4c Trans-Mississippi single with imprint</title>
    <meta property="og:image" content="https://stampauctionnetwork.com/Photos/V/5317/5140.jpg" />
  </head>
  <body>
    <h1>4c Trans-Mississippi single with imprint</h1>
    <a href="https://stampauctionnetwork.com/Photos/V/5317/5140.jpg">Image</a>
  </body>
</html>
"""


DETAIL_PAGE_WITH_BROKEN_EXTRA_IMAGE_HTML = """
<html>
  <head>
    <title>AB Philea lot with one broken extra image</title>
  </head>
  <body>
    <h1>AB Philea lot with one broken extra image</h1>
    <a href="https://www.philea.se/objects/1688/orig/84454.jpg">(Image1)</a>
    <a href="https://www.philea.se/objects/1688/orig/84454-10.jpg">(Image2)</a>
  </body>
</html>
"""


UPA_AUCTION_HTML = """
<html>
  <head>
    <title>Universal Philatelic Auctions Sale - 101</title>
  </head>
  <body>
    <h1>Universal Philatelic Auctions Sale - 101</h1>
    <h2>Wonderful Worldwide Postal Auction with No Buyer's Premium - April 7, 2026</h2>
    <p>There are many POSTAL AUCTIONS but NONE like this.</p>
    <p>Bidding closes at 5pm UK time Tuesday 7th April 2026</p>
    <p>For more information please contact us at:</p>
    <p>Universal Philatelic Auctions</p>
    <p>4 The Old Coalyard</p>
    <p>Northleach, Glos</p>
    <p>GL54 3HE United Kingdom</p>
    <p>Phone: +44 1451 861111</p>
    <p>To request more information by email: bids@upastampauctions.co.uk</p>
    <a href="https://upastampauctions.co.uk">Universal Philatelic Auctions</a>
    <div>Table of Contents</div>
    <a href="https://stampauctionnetwork.com/UP/up1011.cfm">General Lots (1-2)</a>
    <a href="https://stampauctionnetwork.com/UP/up1012.cfm">Worldwide Lots (3-4)</a>
  </body>
</html>
"""


UPA_LOT_PAGE_HTML = """
<html><body>
  <div>General</div>
  <div>Sale No: 101</div>
  <div>Lot No: 1</div>
  <div>Cat No: SG 1 Penny Black (Image)</div>
  <div>Estimate GBP 120.00</div>
  <div>Opening GBP 96.00</div>
  <div>Currently GBP 120.00</div>
  <img src="https://stampauctionnetwork.com/Photos/UP/101/1.jpg" alt="Lot 1" />

  <div>General</div>
  <div>Sale No: 101</div>
  <div>Lot No: 2</div>
  <div>Cat No: SG 2 Twopenny Blue (Image)</div>
  <div>Estimate GBP 220.00</div>
  <div>Opening GBP 176.00</div>
  <div>Sold...GBP 180.00</div>
  <div>Sold For 180</div>
  <div>Closed..Apr-07-2026, 12:00:00 EST</div>
  <img src="https://stampauctionnetwork.com/Photos/UP/101/2.jpg" alt="Lot 2" />
</body></html>
"""


ALDRICH_TABLE_PAGE_HTML = """
<html>
  <head>
    <title>Michael Aldrich Auctions Sale - 118 Page 1</title>
  </head>
  <body>
    <div>Michael Aldrich Auctions Sale - 118</div>
    <div>United States</div>
    <div>PRE 1900 COVERS</div>
    <div>LotNo. Symbol Lot Description Cat. Value</div>
    <div>1</div>
    <div>(210) 2c Red Brown, Tied on small cover to Hartford, Conn. with Oct. 2, 1883 Washington, D.C. CDS.</div>
    <a href="https://aldrichstampsstorage.blob.core.windows.net/photos/160588.jpg">(Image)</a>
    <div>Estimated $ 250-300</div>
    <div>Currently...$105.00</div>
    <div>Will close during Internet Auction</div>
    <div>FDC COVERS</div>
    <div>LotNo. Symbol Lot Description Cat. Value</div>
    <div>2</div>
    <div>(2122a) $10.75 EXPRESS MAIL BOOKLET ON PANDA HANDPAINTED FDC, tied on large cacheted cover.</div>
    <a href="https://aldrichstampsstorage.blob.core.windows.net/photos/160675.jpg">(Image)</a>
    <div>Estimated $ 250-300</div>
    <div>Currently...$80.00</div>
    <a href="https://stampauctionnetwork.com/B/b1182.cfm">Next Page</a>
    <a href="https://stampauctionnetwork.com/B/B118.cfm">Return to Table of Contents</a>
  </body>
</html>
"""


CS658_TABLE_PAGE_HTML = """
<html>
  <head>
    <title>Casa de Subastas de Madrid Sale - 658 Page 12</title>
  </head>
  <body>
    <div>WorldWide continued...</div>
    <table id="CatTable">
      <tr>
        <td>Lot</td>
        <td>Symbol</td>
        <td>Descrip</td>
        <td>Start Bid</td>
      </tr>
      <tr valign="top">
        <td width="6%">221</td>
        <td width="6%">(*)</td>
        <td width="65%" bgcolor="#DDDDDD">
          <a name="Lot221"></a>
          <a href="https://images.soleryllach.com/large/4301515q.jpg" title="Lot 221">
            <img src="https://images.soleryllach.com/large/4301515q.jpg" alt="image" />
          </a>
          Spain, 1850 issue on fragment. Very fine. (Image1)
          <a href="https://images.soleryllach.com/large/4301515q.jpg"><b>(Image1)</b></a>
        </td>
        <td width="23%" align="right">
          Start Bid &#8364;50<br>
          <b><font color="blue">Closing..Apr-17, 02:00 AM</font></b>
        </td>
      </tr>
      <tr valign="top">
        <td width="6%">222</td>
        <td width="6%">**</td>
        <td width="65%" bgcolor="#DDDDDD">
          <a name="Lot222"></a>
          <a href="https://images.soleryllach.com/large/4301516q.jpg" title="Lot 222">
            <img src="https://images.soleryllach.com/large/4301516q.jpg" alt="image" />
          </a>
          Spain, classic issue with unclear starting price. (Image1)
          <a href="https://images.soleryllach.com/large/4301516q.jpg"><b>(Image1)</b></a>
        </td>
        <td width="23%" align="right">
          Start Bid TBD<br>
          <b><font color="blue">Closing..Apr-17, 02:00 AM</font></b>
        </td>
      </tr>
    </table>
    <a href="https://stampauctionnetwork.com/CS/cs65811.cfm">Previous Page</a>
    <a href="https://stampauctionnetwork.com/CS/cs65813.cfm">Next Page</a>
    <a href="https://stampauctionnetwork.com/CS/CS658.cfm">Return to Table of Contents</a>
  </body>
</html>
"""


MC156_TABLE_PAGE_WITH_SECTION_ANCHOR_HTML = """
<html>
  <head>
    <title>Enchères Champagne Auctions Sale - 156 Page 18</title>
  </head>
  <body>
    <table border="0" cellspacing="0" cellpadding="10" width="100%" align="center">
      <tr><td bgcolor="#FFFFFF">
        <a name="102"><h1>COUNTRIES E - F continued...</h1></a>
        <table id="CatTable" width="100%">
          <caption><b><font size="+1"><a name="102">EGYPT continued...</a></font></b></caption>
          <tr valign="top">
            <td width="6%">LotNo.</td>
            <td width="7%">Symbol</td>
            <td width="7%">CatNo.</td>
            <td width="65%" bgcolor="#DDDDDD">Lot Description</td>
            <td valign="bottom" align="right" width="15%"></td>
          </tr>
          <tr valign="top">
            <td width="6%">341</td>
            <td width="7%">X/XX/O</td>
            <td width="7%">&nbsp;</td>
            <td width="65%" bgcolor="#DDDDDD">
              <a name="Lot341"></a>
              <a href="http://enchereschampagne.sdgcpro.ca/156/341_1.jpg" title="Lot 341" class="MagicZoomPlus">
                <img align="left" src="http://enchereschampagne.sdgcpro.ca/156/341_1.jpg" width="300p" alt="image" />
              </a>
              <strong>EGYPT 1866-1963 COLLECTION STAMPS F-VF */**/O.</strong>
              Palo hingeless album with case containing a collection of 541 stamps.
              <a href="http://enchereschampagne.sdgcpro.ca/156/341_1.jpg" target="_blank"><b>(Image1)</b></a>
              <a href="http://enchereschampagne.sdgcpro.ca/156/341_2.jpg" target="_blank"><b>(Image2)</b></a>
            </td>
            <td valign="bottom" align="right" width="15%">
              Est. C$ 225-275<br><br>
              <b><font color="blue">Currently...C$ 200.00<br>Will close during Public Auction</font></b>
            </td>
          </tr>
          <tr valign="top">
            <td width="6%">342</td>
            <td width="7%">X/XX/O</td>
            <td width="7%">&nbsp;</td>
            <td width="65%" bgcolor="#DDDDDD">
              <a name="Lot342"></a>
              <a href="http://enchereschampagne.sdgcpro.ca/156/342_1.jpg" title="Lot 342" class="MagicZoomPlus">
                <img align="left" src="http://enchereschampagne.sdgcpro.ca/156/342_1.jpg" width="300p" alt="image" />
              </a>
              <strong>EGYPT AIRMAIL COLLECTION.</strong>
              Interesting group with better sets.
              <a href="http://enchereschampagne.sdgcpro.ca/156/342_1.jpg" target="_blank"><b>(Image1)</b></a>
              <a href="http://enchereschampagne.sdgcpro.ca/156/342_2.jpg" target="_blank"><b>(Image2)</b></a>
              <a href="http://enchereschampagne.sdgcpro.ca/156/342_3.jpg" target="_blank"><b>(Image3)</b></a>
            </td>
            <td valign="bottom" align="right" width="15%">
              Est. C$ 120-180<br><br>
              <b><font color="blue">Currently...C$ 125.00<br>Will close during Public Auction</font></b>
            </td>
          </tr>
        </table>
        <a href="https://stampauctionnetwork.com/MC/mc15619.cfm">Next Page</a>
        <a href="https://stampauctionnetwork.com/MC/MC156.cfm">Return to Table of Contents</a>
      </td></tr>
    </table>
  </body>
</html>
"""


AB_PHILEA_TABLE_PAGE_HTML = """
<html>
  <head>
    <title>AB Philea Sale - 420 Page 1</title>
  </head>
  <body>
    <div>SWEDEN continued...</div>
    <div>Classics</div>
    <div>LotNo. Symbol Lot Description Cat. Value</div>
    <table>
      <tr valign="top">
        <td width="5%">2002</td>
        <td width="5%">&nbsp;</td>
        <td width="8%">&nbsp;</td>
        <td width="62%" bgcolor="#DDDDDD">
          <a name="Lot2002"></a>
          <a href="https://www.philea.se/objects/1688/orig/54720.jpg" title="Lot 2002" class="MagicZoomPlus">
            <img align="left" src="https://www.philea.se/objects/1688/orig/54720.jpg" width="300p" alt="image" />
          </a>
          Sweden, Facit 8 or Scott 8 used, 8 skill yellow. (Image1)
          <a href="https://www.philea.se/objects/1688/orig/54720.jpg" target="_blank"><b>(Image1)</b></a>
        </td>
        <td valign="bottom" align="right" width="20%">
          Estimate US$ 32<br><br>
          <b><font color="blue">Currently...US$ 32.00<br>Closing..Apr-15, 03:00 AM</font></b>
        </td>
      </tr>
      <tr valign="top">
        <td width="5%">2003</td>
        <td width="5%">&nbsp;</td>
        <td width="8%">&nbsp;</td>
        <td width="62%" bgcolor="#DDDDDD">
          <a name="Lot2003"></a>
          <a href="https://www.philea.se/objects/1688/orig/54758.jpg" title="Lot 2003" class="MagicZoomPlus">
            <img align="left" src="https://www.philea.se/objects/1688/orig/54758.jpg" width="300p" alt="image" />
          </a>
          Sweden, Facit 30 or Scott 30 used. (Image1) (Image2)
          <a href="https://www.philea.se/objects/1688/orig/54758.jpg" target="_blank"><b>(Image1)</b></a>
          <a href="https://www.philea.se/objects/1688/orig/54758-2.jpg" target="_blank"><b>(Image2)</b></a>
          <p>
            <a href="https://www.philea.se/objects/1688/orig/54758-2.jpg" title="Lot 2003 (2)" class="MagicZoomPlus">
              <img align="left" src="https://www.philea.se/objects/1688/orig/54758-2.jpg" width="200p" alt="image" />
            </a>
          </p>
        </td>
        <td valign="bottom" align="right" width="20%">
          Estimate US$ 156<br><br>
          <b><font color="blue">Currently...US$ 156.00<br>Closing..Apr-15, 03:00 AM</font></b>
        </td>
      </tr>
      <tr valign="top">
        <td width="5%">2004</td>
        <td width="5%">&nbsp;</td>
        <td width="8%">&nbsp;</td>
        <td width="62%" bgcolor="#DDDDDD">
          <a name="Lot2004"></a>
          <a href="https://www.philea.se/objects/1688/orig/54777.jpg" title="Lot 2004" class="MagicZoomPlus">
            <img align="left" src="https://www.philea.se/objects/1688/orig/54777.jpg" width="300p" alt="image" />
          </a>
          Sweden, Facit 8a or Scott 8a used, 8 skill orange-yellow. Postal:<br>2500<br>SEK (Image1)
          <a href="https://www.philea.se/objects/1688/orig/54777.jpg" target="_blank"><b>(Image1)</b></a>
        </td>
        <td valign="bottom" align="right" width="20%">
          Estimate US$ 73<br><br>
          <b><font color="blue">Currently...US$ 73.00<br>Closing..Apr-15, 03:00 AM</font></b>
        </td>
      </tr>
    </table>
    <a href="https://stampauctionnetwork.com/ZA/za4202.cfm">Next Page</a>
    <a href="https://stampauctionnetwork.com/ZA/ZA420.cfm">Return to Table of Contents</a>
  </body>
</html>
"""


AB_PHILEA_COMPACT_PAGE_HTML = """
<html>
  <head>
    <title>AB Philea Sale - 420 Page 23</title>
  </head>
  <body>
    <div>SWEDEN continued...</div>
    <div>Officials, perf 13 continued...</div>
    <div>Lot Symbol Catalog No. Descrip Opening</div>
    <div>2442 Image: og Sweden, Facit Tj24A, 1 krona blue/brown, perf 13, type I. Some short perfs. F 4500 (Image1) Estimate US$ 42</div>
    <div>Currently...US$ 42.00</div>
    <div>Closing..Apr-15, 03:00 AM</div>
    <div>2443 Image: c Sweden, Facit Tj27, 29 cover on return receipt form for a registered letter. (Image1) (Image2) Estimate US$ TBD</div>
    <div>Currently...US$ 42.00</div>
    <div>Closing..Apr-15, 03:00 AM</div>
    <a href="https://stampauctionnetwork.com/ZA/za42019.cfm">Previous Page</a>
    <a href="https://stampauctionnetwork.com/ZA/za42024.cfm">Next Page</a>
    <a href="https://stampauctionnetwork.com/ZA/ZA420.cfm">Return to Table of Contents</a>
    <a href="https://stampauctionnetwork.com/assets/za420/2442-1.jpg">(Image1)</a>
    <a href="https://stampauctionnetwork.com/assets/za420/2443-1.jpg">(Image1)</a>
    <a href="https://stampauctionnetwork.com/assets/za420/2443-2.jpg">(Image2)</a>
  </body>
</html>
"""


AB_PHILEA_COMPACT_PAGE_NO_PRICE_HTML = """
<html>
  <head>
    <title>AB Philea Sale - 420 Page 24</title>
  </head>
  <body>
    <div>SWEDEN continued...</div>
    <div>Officials, perf 13 continued...</div>
    <div>Lot Symbol Catalog No. Descrip Opening</div>
    <div>2446 Image: nh Sweden, Facit Tj55, 20 ore green with upright posthorn. (Image1)</div>
    <a href="https://stampauctionnetwork.com/ZA/za42025.cfm">Next Page</a>
    <a href="https://stampauctionnetwork.com/assets/za420/2446-1.jpg">(Image1)</a>
  </body>
</html>
"""


AB_PHILEA_COMPACT_FLAT_TEXT_HTML = """
<html>
  <head>
    <title>AB Philea Sale - 420 Page 25</title>
  </head>
  <body>
    <div>SWEDEN continued... Officials, perf 13 continued... Lot Symbol Catalog No. Descrip Opening 2482 Image: og Sweden, Official Facit Tj82, 10 ore blue. Some short perfs. (Image1) Estimate US$ 42 Currently...US$ 42.00 Closing..Apr-15, 03:00 AM 2483 Image: c Sweden, Official Facit Tj83 on piece. (Image1) Estimate US$ TBD Currently...US$ 42.00 Closing..Apr-15, 03:00 AM Previous Page Next Page Return to Table of Contents</div>
    <a href="https://stampauctionnetwork.com/assets/za420/2482-1.jpg">(Image1)</a>
    <a href="https://stampauctionnetwork.com/assets/za420/2483-1.jpg">(Image1)</a>
  </body>
</html>
"""


AB_PHILEA_COMPACT_FLAT_TEXT_WITH_FOOTER_HTML = """
<html>
  <head>
    <title>AB Philea Sale - 420 Page 24</title>
  </head>
  <body>
    <div>SWEDEN continued... Circle type with posthorn (F 40-51) Lots (2462-2481) Lot Symbol Catalog No. Descrip Opening 2462 Image: og Sweden, 3 ore yellowish brown. Superb cancellation ENGELHOLM 22.1.1891. (Image1) Estimate US$ 28 Currently...US$ 32.00 Closing..Apr-15, 03:00 AM 2481 Image: c Sweden, 20 ore light orange-red. EXCELLENT cancellation GISLAVED 29.4.1889. (Image1) Estimate US$ 40 Currently...US$ 40.00 Closing..Apr-15, 03:00 AM 9459 or email support@stampauctionnetwork.com We can help you evaluate or sell your collection so... Click here for help selling your Collection Previous Page Next Page Return to Table of Contents</div>
    <a href="https://stampauctionnetwork.com/assets/za420/2462-1.jpg">(Image1)</a>
    <a href="https://stampauctionnetwork.com/assets/za420/2481-1.jpg">(Image1)</a>
  </body>
</html>
"""


AB_PHILEA_COMPACT_FLAT_TEXT_WITH_EMBEDDED_YEARS_HTML = """
<html>
  <head>
    <title>AB Philea Sale - 420 Page 1</title>
  </head>
  <body>
    <div>SWEDEN continued... Foreign-related covers Lot Symbol Catalog No. Descrip Opening 2015 Image: Sweden, cover sent from AMSTERDAM 16.8.1855 via KS&amp;NPA HAMBURG 18.8.1855 and HELSINGBORG 20.8.1855 to Gavle. (Image1) Estimate US$ 42 Currently...US$ 42.00 Closing..Apr-15, 03:00 AM 2016 Image: Sweden, cover sent from HELSINGOR 25.10.1866 via HELSINGBORG 26.10.1866 to Finland. (Image1) Estimate US$ 32 Currently...US$ 32.00 Closing..Apr-15, 03:00 AM Previous Page Next Page Return to Table of Contents</div>
    <a name="Lot2015"></a>
    <a href="https://www.philea.se/objects/1688/orig/58085.jpg">(Image1)</a>
    <a name="Lot2016"></a>
    <a href="https://www.philea.se/objects/1688/orig/54720.jpg">(Image1)</a>
  </body>
</html>
"""


class FakeResponse:
    """Simple fake response used for job-cap tests."""

    def __init__(
        self,
        text: str = "",
        *,
        status_code: int = 200,
        url: str = "",
        content: bytes | None = None,
        headers: Mapping[str, Any] | None = None,
    ):
        self.text = text
        self.status_code = status_code
        self.url = url
        self.content = content if content is not None else text.encode("utf-8")
        self.headers = dict(headers or {})

    def raise_for_status(self):
        """Raise on HTTP failures."""
        if self.status_code >= 400:
            raise RuntimeError(f"status {self.status_code}")
        return None


class FakeWorker:
    """Minimal worker stub with a pool and logger."""

    def __init__(self, pool: SQLitePool):
        self.pool = pool
        self.log_messages: list[tuple[str, tuple[Any, ...]]] = []
        self.logger = self

    def info(self, message: str, *args: Any):
        """Capture log messages for assertions."""
        self.log_messages.append((message, args))


def _job(*, required_capability: str, payload=None) -> JobDetail:
    """Build a claimed job detail for one test."""
    return JobDetail.model_validate(
        {
            "id": f"dispatcher-job:{required_capability.lower().replace(' ', '-')}",
            "required_capability": required_capability,
            "payload": payload or {},
            "status": "claimed",
            "claimed_by": "worker-a",
            "attempts": 1,
            "max_attempts": 5,
        }
    )


def _sales_listing_rows_by_source_id(pool: SQLitePool) -> dict[str, dict[str, Any]]:
    """Return persisted SAN sales-listing rows keyed by source id."""
    rows = pool._GetTableData(TABLE_SALES_LISTINGS, table_schema=sales_listings_table_schema())
    return {
        str(row.get("source_listing_id") or "").strip(): dict(row)
        for row in rows
        if isinstance(row, Mapping) and str(row.get("source_listing_id") or "").strip()
    }


def _jobs_for_capability(pool: SQLitePool, capability: str) -> list[dict[str, Any]]:
    """Return queued dispatcher jobs for one capability."""
    return [dict(row) for row in pool._GetTableData(TABLE_JOBS) if row["required_capability"] == capability]


def _web_page_rows_by_source_url(pool: SQLitePool) -> dict[str, dict[str, Any]]:
    """Return cached web-page rows keyed by source URL."""
    rows = pool._GetTableData(TABLE_WEB_PAGES, table_schema=web_pages_table_schema())
    return {
        str(row.get("source_url") or "").strip(): dict(row)
        for row in rows
        if isinstance(row, Mapping) and str(row.get("source_url") or "").strip()
    }


def test_stamp_auction_network_catalog_job_queues_seed_pages(tmp_path):
    """Catalog job should fan out configured SAN seed pages."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    cap = StampAuctionNetworkJobCap(
        source_pages=[
            {"page_url": "https://stampauctionnetwork.com/auctions.cfm", "label": "Auctions"},
            {"page_url": "https://stampauctionnetwork.com/pr.cfm", "label": "Prices realized"},
        ]
    ).bind_worker(worker)

    result = cap.finish(_job(required_capability="StampAuctionNetwork Catalog"))
    assert result.status == "completed"
    assert result.result_summary["queued_pages_this_run"] == 2

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["payload"]["page_url"])
    assert len(queued_jobs) == 2
    assert [row["required_capability"] for row in queued_jobs] == [
        "stampauctionnetwork page",
        "stampauctionnetwork page",
    ]
    assert [row["payload"]["page_url"] for row in queued_jobs] == [
        "https://stampauctionnetwork.com/auctions.cfm",
        "https://stampauctionnetwork.com/pr.cfm",
    ]


def test_stamp_auction_network_page_job_discovers_sale_pages_from_auctions_index(tmp_path):
    """Page job should parse the auction index and queue sale pages."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://stampauctionnetwork.com/auctions.cfm"
        return FakeResponse(AUCTIONS_HTML, url=url)

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={"page_url": "https://stampauctionnetwork.com/auctions.cfm", "page_label": "Auctions"},
        )
    )
    assert result.status == "completed"
    assert result.result_summary["persisted_auction_rows"] == 0
    assert result.result_summary["queued_pages_this_run"] == 2
    assert result.result_summary["queued_listings_this_run"] == 0

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["payload"]["page_url"])
    assert len(queued_jobs) == 2
    assert [row["payload"]["page_url"] for row in queued_jobs] == [
        "https://stampauctionnetwork.com/MC/MC156.cfm",
        "https://stampauctionnetwork.com/V/V5317.cfm",
    ]
    assert all(int(row["priority"] or 0) == PRIORITY_PAGE_NEW_AUCTION for row in queued_jobs)
    queued_by_url = {row["payload"]["page_url"]: row["payload"] for row in queued_jobs}
    assert queued_by_url["https://stampauctionnetwork.com/MC/MC156.cfm"]["sale_title"] == "Encheres Champagne Auctions Sale - 156"
    assert queued_by_url["https://stampauctionnetwork.com/MC/MC156.cfm"]["firm_code"] == "MC"
    assert queued_by_url["https://stampauctionnetwork.com/MC/MC156.cfm"]["source_auction_id"] == "mc-156"
    assert queued_by_url["https://stampauctionnetwork.com/MC/MC156.cfm"]["auctioneer_id"] == "stampauctionnetwork:auctioneer:mc"
    assert queued_by_url["https://stampauctionnetwork.com/MC/MC156.cfm"]["auction_id"] == "stampauctionnetwork:auction:mc-156"
    assert queued_by_url["https://stampauctionnetwork.com/V/V5317.cfm"]["sale_title"] == (
        "Weekly Online Sales - a Division of Daniel F. Kelleher Auctions Sale - 5317"
    )
    assert queued_by_url["https://stampauctionnetwork.com/V/V5317.cfm"]["firm_code"] == "V"
    assert queued_by_url["https://stampauctionnetwork.com/V/V5317.cfm"]["source_auction_id"] == "v-5317"
    assert queued_by_url["https://stampauctionnetwork.com/V/V5317.cfm"]["auctioneer_id"] == "stampauctionnetwork:auctioneer:v"
    assert queued_by_url["https://stampauctionnetwork.com/V/V5317.cfm"]["auction_id"] == "stampauctionnetwork:auction:v-5317"
    assert pool._GetTableData(TABLE_AUCTIONEERS, table_schema=auctioneers_table_schema()) == []
    assert pool._GetTableData(TABLE_AUCTIONS, table_schema=auctions_table_schema()) == []


def test_stamp_auction_network_page_job_caches_fetched_html_and_refreshes_on_demand(tmp_path):
    """SAN page jobs should persist fetched HTML in the shared cache and reuse it until forced refresh."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    request_urls: list[str] = []
    responses = [AUCTIONS_HTML, UPDATED_AUCTIONS_HTML]

    def fake_request_get(url, **kwargs):
        request_urls.append(url)
        return FakeResponse(
            responses[len(request_urls) - 1],
            url=url,
            headers={
                "Content-Type": "text/html; charset=utf-8",
                "ETag": f"etag-{len(request_urls)}",
                "Last-Modified": "Sat, 12 Apr 2026 00:00:00 GMT",
            },
        )

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    first = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={"page_url": "https://stampauctionnetwork.com/auctions.cfm", "page_label": "Auctions"},
        )
    )
    second = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={"page_url": "https://stampauctionnetwork.com/auctions.cfm", "page_label": "Auctions"},
        )
    )
    third = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={
                "page_url": "https://stampauctionnetwork.com/auctions.cfm",
                "page_label": "Auctions",
                "refresh_item": True,
            },
        )
    )

    assert first.status == "completed"
    assert second.status == "completed"
    assert third.status == "completed"
    assert request_urls == [
        "https://stampauctionnetwork.com/auctions.cfm",
        "https://stampauctionnetwork.com/auctions.cfm",
    ]
    assert first.result_summary["page_cache_hit"] is False
    assert second.result_summary["page_cache_hit"] is True
    assert third.result_summary["page_cache_hit"] is False
    assert second.result_summary["page_fetch_source"] == "cache"
    assert third.result_summary["page_fetch_source"] == "network"

    cached_rows = _web_page_rows_by_source_url(pool)
    assert list(cached_rows) == ["https://stampauctionnetwork.com/auctions.cfm"]
    cached_row = cached_rows["https://stampauctionnetwork.com/auctions.cfm"]
    assert cached_row["provider"] == "stampauctionnetwork"
    assert cached_row["page_kind"] == "auction_index"
    assert cached_row["content_type"] == "text/html; charset=utf-8"
    assert cached_row["etag"] == "etag-2"
    assert "AB Philea Online Stamp Auction" in cached_row["html_text"]
    assert "AB Philea Online Stamp Auction - April 15-16, 2026" in cached_row["text_content"]


def test_stamp_auction_network_duplicate_page_skip_log_includes_reason_and_proof(tmp_path):
    """Duplicate SAN page skips should log both the reason and proof of the existing job."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    cap = StampAuctionNetworkJobCap(media_root=str(tmp_path / "media")).bind_worker(worker)

    first = cap._queue_page_job(
        page_url="https://stampauctionnetwork.com/ZA/ZA420.cfm",
        page_label="AB Philea Online Stamp Auction - April 15-16, 2026",
        sale_title="AB Philea Online Stamp Auction - April 15-16, 2026",
        auction_context={
            "firm_code": "ZA",
            "sale_number": "420",
            "source_auction_id": "za-420",
            "auction_id": "stampauctionnetwork:auction:za-420",
            "auctioneer_id": "stampauctionnetwork:auctioneer:za",
            "auction_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm",
        },
    )
    assert first["queued"] is True

    second = cap._queue_page_job(
        page_url="https://stampauctionnetwork.com/ZA/ZA420.cfm",
        page_label="AB Philea Online Stamp Auction - April 15-16, 2026",
        sale_title="AB Philea Online Stamp Auction - April 15-16, 2026",
        auction_context={
            "firm_code": "ZA",
            "sale_number": "420",
            "source_auction_id": "za-420",
            "auction_id": "stampauctionnetwork:auction:za-420",
            "auctioneer_id": "stampauctionnetwork:auctioneer:za",
            "auction_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm",
        },
        discovered_from="https://stampauctionnetwork.com/ZA/za42025.cfm",
        relationship="auction_landing",
    )
    assert second["queued"] is False
    message, args = worker.log_messages[-1]
    rendered = message % args
    assert "skip_reason=auction_landing_already_known" in rendered
    assert "proof=job_id=" in rendered
    assert "source_url=https://stampauctionnetwork.com/ZA/ZA420.cfm" in rendered
    assert "discovered_from=https://stampauctionnetwork.com/ZA/za42025.cfm" in rendered
    assert "relationship=auction_landing" in rendered


def test_stamp_auction_network_existing_dispatcher_job_avoids_full_table_scan(tmp_path):
    """Logical-key duplicate checks should not read the entire dispatcher job table."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    cap = StampAuctionNetworkJobCap(media_root=str(tmp_path / "media")).bind_worker(worker)
    ensure_dispatcher_tables(pool, [TABLE_JOBS])

    page_url = "https://stampauctionnetwork.com/ZA/ZA420.cfm"
    logical_job_key = cap._page_logical_job_key(page_url)
    existing_job = build_dispatch_job(
        required_capability=cap.PAGE_CAPABILITY,
        payload={"page_url": page_url},
        job_id="dispatcher-job:stampauctionnetwork-page:reissued-za420",
        source_url=page_url,
        metadata={"stamp_auction_network": {"logical_job_key": logical_job_key}},
    )
    assert pool._Insert(TABLE_JOBS, existing_job.to_row())

    original_get_table_data = pool._GetTableData

    def guarded_get_table_data(table_name, id_or_where=None, table_schema=None):
        if table_name == TABLE_JOBS and not id_or_where:
            raise AssertionError("Full dispatcher_jobs scans are not allowed in SAN duplicate checks.")
        return original_get_table_data(table_name, id_or_where=id_or_where, table_schema=table_schema)

    pool._GetTableData = guarded_get_table_data  # type: ignore[method-assign]

    matched = cap._existing_dispatcher_job(
        job_id="dispatcher-job:stampauctionnetwork-page:za420-deterministic",
        logical_job_key=logical_job_key,
        statuses={"queued", "claimed", "unfinished", "retry", "completed"},
    )
    assert matched is not None
    assert matched["id"] == "dispatcher-job:stampauctionnetwork-page:reissued-za420"


def test_stamp_auction_network_page_job_ignores_catalog_and_unrelated_links_from_sale_page(tmp_path):
    """Sale pages should only follow the SAN crawl whitelist, not arbitrary links."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://stampauctionnetwork.com/V/V5317.cfm"
        return FakeResponse(SALE_PAGE_HTML, url=url)

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={"page_url": "https://stampauctionnetwork.com/V/V5317.cfm"},
        )
    )
    assert result.status == "completed"
    assert result.result_summary["queued_pages_this_run"] == 0
    assert result.result_summary["queued_listings_this_run"] == 0

    assert pool._GetTableData(TABLE_JOBS) == []


def test_stamp_auction_network_page_job_skips_navigation_toc_pages_without_fetch(tmp_path):
    """Navigation-only SAN TOC page jobs should complete without issuing HTTP requests."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        raise AssertionError(f"navigation page should not be fetched: {url}")

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={
                "page_url": "https://stampauctionnetwork.com/iCatalog2TOC.cfm?MAJGROUP=BANKNOTES&SrchFirm=ZA&SrchSale=420",
                "page_label": "BANKNOTES",
                "sale_title": "AB Philea Online Stamp Auction - April 15-16, 2026",
                "firm_code": "ZA",
                "sale_number": "420",
                "source_auction_id": "za-420",
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["skipped_navigation_page"] is True
    assert result.result_summary["queued_pages_this_run"] == 0
    assert result.result_summary["queued_listings_this_run"] == 0
    assert pool._GetTableData(TABLE_JOBS) == []


def test_stamp_auction_network_page_job_persists_auctioneer_and_auction_rows(tmp_path):
    """Auction landing pages should persist normalized auctioneer and auction rows."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://stampauctionnetwork.com/UP/UP101.cfm"
        return FakeResponse(UPA_AUCTION_HTML, url=url)

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={"page_url": "https://stampauctionnetwork.com/UP/UP101.cfm"},
        )
    )

    assert result.status == "completed"
    assert result.result_summary["persisted_auction_rows"] == 2
    assert result.result_summary["queued_pages_this_run"] == 1

    auctioneers = pool._GetTableData(
        TABLE_AUCTIONEERS,
        "stampauctionnetwork:auctioneer:up",
        table_schema=auctioneers_table_schema(),
    )
    auctions = pool._GetTableData(
        TABLE_AUCTIONS,
        "stampauctionnetwork:auction:up-101",
        table_schema=auctions_table_schema(),
    )

    assert len(auctioneers) == 1
    assert auctioneers[0]["name"] == "Universal Philatelic Auctions"
    assert auctioneers[0]["contact_email"] == "bids@upastampauctions.co.uk"

    assert len(auctions) == 1
    assert auctions[0]["title"] == "Universal Philatelic Auctions Sale - 101"
    assert auctions[0]["auctioneer_id"] == "stampauctionnetwork:auctioneer:up"
    assert auctions[0]["lot_count"] == 4
    assert auctions[0]["source_url"] == "https://stampauctionnetwork.com/UP/UP101.cfm"

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["payload"]["page_url"])
    assert [row["payload"]["page_url"] for row in queued_jobs] == ["https://stampauctionnetwork.com/UP/up1011.cfm"]
    assert all(int(row["priority"] or 0) == PRIORITY_PAGE_SAME_AUCTION for row in queued_jobs)
    assert all(row["payload"]["auction_url"] == "https://stampauctionnetwork.com/UP/UP101.cfm" for row in queued_jobs)


def test_stamp_auction_network_page_job_repairs_legacy_index_context_on_sale_pages(tmp_path):
    """Legacy sale-page jobs queued from the index should recover the real auction title and URL."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://stampauctionnetwork.com/UP/UP101.cfm"
        return FakeResponse(UPA_AUCTION_HTML, url=url)

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={
                "page_url": "https://stampauctionnetwork.com/UP/UP101.cfm",
                "page_label": "Universal Philatelic Auctions Wonderful Worldwide Postal Auction with No Buyer's Premium - April 7, 2026",
                "sale_title": "StampAuctionNetwork auctions",
                "firm_code": "UP",
                "sale_number": "101",
                "source_auction_id": "up-101",
                "auction_id": "stampauctionnetwork:auction:auction",
                "auctioneer_id": "stampauctionnetwork:auctioneer:auctioneer",
                "auction_url": "https://stampauctionnetwork.com/auctions.cfm",
            },
        )
    )

    assert result.status == "completed"
    auctions = pool._GetTableData(
        TABLE_AUCTIONS,
        "stampauctionnetwork:auction:up-101",
        table_schema=auctions_table_schema(),
    )
    assert len(auctions) == 1
    assert auctions[0]["title"] == "Universal Philatelic Auctions Wonderful Worldwide Postal Auction with No Buyer's Premium - April 7, 2026"
    assert auctions[0]["source_url"] == "https://stampauctionnetwork.com/UP/UP101.cfm"

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["payload"]["page_url"])
    assert [row["payload"]["page_url"] for row in queued_jobs] == ["https://stampauctionnetwork.com/UP/up1011.cfm"]
    assert all(row["payload"]["sale_title"] == auctions[0]["title"] for row in queued_jobs)
    assert all(row["payload"]["auction_url"] == "https://stampauctionnetwork.com/UP/UP101.cfm" for row in queued_jobs)


def test_stamp_auction_network_page_job_parses_child_lot_pages_with_canonical_auction_links(tmp_path):
    """Auction child pages should keep lots attached to the parent auction context."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://stampauctionnetwork.com/UP/up1011.cfm"
        return FakeResponse(UPA_LOT_PAGE_HTML, url=url)

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={
                "page_url": "https://stampauctionnetwork.com/UP/up1011.cfm",
                "sale_title": "Universal Philatelic Auctions Sale - 101",
                "firm_code": "UP",
                "sale_number": "101",
                "source_auction_id": "up-101",
                "auction_id": "stampauctionnetwork:auction:up-101",
                "auctioneer_id": "stampauctionnetwork:auctioneer:up",
                "auction_url": "https://stampauctionnetwork.com/UP/UP101.cfm",
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["queued_listings_this_run"] == 2
    assert result.result_summary["persisted_listings_this_run"] == 2
    assert result.result_summary["queued_image_jobs_this_run"] == 2

    rows = _sales_listing_rows_by_source_id(pool)
    assert sorted(rows) == ["up-101-1", "up-101-2"]
    assert [rows[source_listing_id]["listing_url"] for source_listing_id in sorted(rows)] == [
        "https://stampauctionnetwork.com/UP/UP101.cfm#2",
        "https://stampauctionnetwork.com/UP/UP101.cfm#2",
    ]
    assert [rows[source_listing_id]["payload"]["detail_url"] for source_listing_id in sorted(rows)] == [
        "https://stampauctionnetwork.com/UP/up1011.cfm",
        "https://stampauctionnetwork.com/UP/up1011.cfm",
    ]
    assert [rows[source_listing_id]["search_page"] for source_listing_id in sorted(rows)] == [2, 2]
    assert float(rows["up-101-1"]["estimate_amount"]) == 120.0
    assert float(rows["up-101-2"]["hammer_price_amount"]) == 180.0


def test_stamp_auction_network_page_job_repairs_legacy_index_context_on_child_pages(tmp_path):
    """Legacy child-page jobs queued from the index should recover the parent auction URL."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://stampauctionnetwork.com/UP/up1011.cfm"
        return FakeResponse(UPA_LOT_PAGE_HTML, url=url)

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={
                "page_url": "https://stampauctionnetwork.com/UP/up1011.cfm",
                "page_label": "Universal Philatelic Auctions Wonderful Worldwide Postal Auction with No Buyer's Premium - April 7, 2026",
                "sale_title": "StampAuctionNetwork auctions",
                "firm_code": "UP",
                "sale_number": "101",
                "source_auction_id": "up-101",
                "auction_id": "stampauctionnetwork:auction:auction",
                "auctioneer_id": "stampauctionnetwork:auctioneer:auctioneer",
                "auction_url": "https://stampauctionnetwork.com/auctions.cfm",
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["persisted_auction_rows"] == 0
    auctions = pool._GetTableData(TABLE_AUCTIONS, table_schema=auctions_table_schema())
    assert len(auctions) == 1
    assert auctions[0]["source_url"] == "https://stampauctionnetwork.com/UP/UP101.cfm"

    rows = _sales_listing_rows_by_source_id(pool)
    assert [rows[source_listing_id]["listing_url"] for source_listing_id in sorted(rows)] == [
        "https://stampauctionnetwork.com/UP/UP101.cfm#2",
        "https://stampauctionnetwork.com/UP/UP101.cfm#2",
    ]
    assert [rows[source_listing_id]["search_page"] for source_listing_id in sorted(rows)] == [2, 2]


def test_stamp_auction_network_page_job_parses_live_table_style_child_pages(tmp_path):
    """Table-style SAN child pages should queue listings even without Sale No/Lot No field blocks."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://stampauctionnetwork.com/B/b1181.cfm"
        return FakeResponse(ALDRICH_TABLE_PAGE_HTML, url=url)

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={
                "page_url": "https://stampauctionnetwork.com/B/b1181.cfm",
                "sale_title": "Michael Aldrich Auctions/ABC Auctions U.S. and Worldwide Stamps and Covers - April 16-18, 2026",
                "firm_code": "B",
                "sale_number": "118",
                "source_auction_id": "b-118",
                "auction_id": "stampauctionnetwork:auction:b-118",
                "auctioneer_id": "stampauctionnetwork:auctioneer:b",
                "auction_url": "https://stampauctionnetwork.com/B/B118.cfm",
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["persisted_auction_rows"] == 0
    assert result.result_summary["queued_pages_this_run"] == 1
    assert result.result_summary["queued_listings_this_run"] == 2

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: (row["required_capability"], row["id"]))
    assert [row["required_capability"] for row in queued_jobs] == [
        "stampauctionnetwork image",
        "stampauctionnetwork image",
        "stampauctionnetwork page",
    ]
    image_jobs = [row for row in queued_jobs if row["required_capability"] == "stampauctionnetwork image"]
    page_jobs = sorted(
        [row for row in queued_jobs if row["required_capability"] == "stampauctionnetwork page"],
        key=lambda row: row["payload"]["page_url"],
    )
    assert [row["payload"]["page_url"] for row in page_jobs] == ["https://stampauctionnetwork.com/B/b1182.cfm"]
    rows = _sales_listing_rows_by_source_id(pool)
    assert sorted(rows) == ["b-118-1", "b-118-2"]
    assert [rows[source_listing_id]["listing_url"] for source_listing_id in sorted(rows)] == [
        "https://stampauctionnetwork.com/B/B118.cfm#2",
        "https://stampauctionnetwork.com/B/B118.cfm#2",
    ]
    assert [rows[source_listing_id]["payload"]["detail_url"] for source_listing_id in sorted(rows)] == [
        "https://stampauctionnetwork.com/B/b1181.cfm",
        "https://stampauctionnetwork.com/B/b1181.cfm",
    ]
    assert [rows[source_listing_id]["image_url"] for source_listing_id in sorted(rows)] == [
        "https://aldrichstampsstorage.blob.core.windows.net/photos/160588.jpg",
        "https://aldrichstampsstorage.blob.core.windows.net/photos/160675.jpg",
    ]
    assert [job["payload"]["source_listing_id"] for job in image_jobs] == ["b-118-1", "b-118-2"]
    assert rows["b-118-1"]["title"].startswith("2c Red Brown")
    assert rows["b-118-1"]["payload"]["catalog_number"] == "210"
    assert rows["b-118-1"]["payload"]["major_group"] == "United States"
    assert rows["b-118-1"]["payload"]["sub_group"] == "PRE 1900 COVERS"
    assert rows["b-118-2"]["payload"]["sub_group"] == "FDC COVERS"
    assert float(rows["b-118-1"]["estimate_amount"]) == 250.0
    assert float(rows["b-118-1"]["payload"]["current_amount"]) == 105.0


def test_stamp_auction_network_page_job_keeps_table_style_images_scoped_to_each_lot(tmp_path):
    """Table-style SAN pages should keep multi-image lots from shifting later lot images."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://stampauctionnetwork.com/ZA/za4201.cfm"
        return FakeResponse(AB_PHILEA_TABLE_PAGE_HTML, url=url)

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={
                "page_url": "https://stampauctionnetwork.com/ZA/za4201.cfm",
                "sale_title": "AB Philea Online Stamp Auction - April 15-16, 2026",
                "firm_code": "ZA",
                "sale_number": "420",
                "source_auction_id": "za-420",
                "auction_id": "stampauctionnetwork:auction:za-420",
                "auctioneer_id": "stampauctionnetwork:auctioneer:za",
                "auction_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm",
            },
        )
    )

    assert result.status == "completed"
    rows = _sales_listing_rows_by_source_id(pool)
    assert sorted(rows) == ["za-420-2002", "za-420-2003", "za-420-2004"]
    assert rows["za-420-2002"]["image_urls"] == ["https://www.philea.se/objects/1688/orig/54720.jpg"]
    assert rows["za-420-2003"]["image_urls"] == [
        "https://www.philea.se/objects/1688/orig/54758.jpg",
        "https://www.philea.se/objects/1688/orig/54758-2.jpg",
    ]
    assert rows["za-420-2004"]["image_urls"] == ["https://www.philea.se/objects/1688/orig/54777.jpg"]
    assert rows["za-420-2004"]["image_url"] == "https://www.philea.se/objects/1688/orig/54777.jpg"


def test_stamp_auction_network_page_job_parses_start_bid_table_rows_and_keeps_raw_html(tmp_path):
    """HTML table rows with lot anchors should persist even when start-bid text is not numeric."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://stampauctionnetwork.com/CS/cs65812.cfm"
        return FakeResponse(CS658_TABLE_PAGE_HTML, url=url)

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={
                "page_url": "https://stampauctionnetwork.com/CS/cs65812.cfm",
                "sale_title": "Casa de Subastas de Madrid Numismatic & Philately Auction - April 17-18, 2026",
                "firm_code": "CS",
                "sale_number": "658",
                "source_auction_id": "cs-658",
                "auction_id": "stampauctionnetwork:auction:cs-658",
                "auctioneer_id": "stampauctionnetwork:auctioneer:cs",
                "auction_url": "https://stampauctionnetwork.com/CS/CS658.cfm",
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["queued_listings_this_run"] == 2
    rows = _sales_listing_rows_by_source_id(pool)
    assert sorted(rows) == ["cs-658-221", "cs-658-222"]
    assert rows["cs-658-221"]["image_urls"] == ["https://images.soleryllach.com/large/4301515q.jpg"]
    assert rows["cs-658-221"]["payload"]["opening_text"] == "Start Bid €50"
    assert float(rows["cs-658-221"]["price_amount"]) == 50.0
    assert "Lot221" in rows["cs-658-221"]["payload"]["raw_block_html"]
    assert rows["cs-658-222"]["payload"]["price_text"] == "Start Bid TBD"
    assert float(rows["cs-658-222"]["price_amount"]) == -1.0
    assert rows["cs-658-222"]["title"].startswith("classic issue")


def test_stamp_auction_network_page_job_ignores_section_anchors_on_mc_table_pages(tmp_path):
    """Section anchors like NAME="102" should not become fake MC lot rows or absorb page-wide images."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://stampauctionnetwork.com/MC/mc15618.cfm"
        return FakeResponse(MC156_TABLE_PAGE_WITH_SECTION_ANCHOR_HTML, url=url)

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={
                "page_url": "https://stampauctionnetwork.com/MC/mc15618.cfm",
                "sale_title": "Enchères Champagne Auctions (MTM International) Public Live Auction #156 - April 25-May3, 2026",
                "firm_code": "MC",
                "sale_number": "156",
                "source_auction_id": "mc-156",
                "auction_id": "stampauctionnetwork:auction:mc-156",
                "auctioneer_id": "stampauctionnetwork:auctioneer:mc",
                "auction_url": "https://stampauctionnetwork.com/MC/MC156.cfm",
            },
        )
    )

    assert result.status == "completed"
    rows = _sales_listing_rows_by_source_id(pool)
    assert sorted(rows) == ["mc-156-341", "mc-156-342"]
    assert "mc-156-102" not in rows
    assert rows["mc-156-341"]["title"].startswith("EGYPT 1866-1963 COLLECTION STAMPS")
    assert rows["mc-156-341"]["image_urls"] == [
        "http://enchereschampagne.sdgcpro.ca/156/341_1.jpg",
        "http://enchereschampagne.sdgcpro.ca/156/341_2.jpg",
    ]
    assert rows["mc-156-342"]["image_urls"] == [
        "http://enchereschampagne.sdgcpro.ca/156/342_1.jpg",
        "http://enchereschampagne.sdgcpro.ca/156/342_2.jpg",
        "http://enchereschampagne.sdgcpro.ca/156/342_3.jpg",
    ]
    assert rows["mc-156-341"]["image_url"] != rows["mc-156-342"]["image_url"]


def test_stamp_auction_network_page_job_parses_compact_ab_philea_style_pages(tmp_path):
    """Compact SAN child pages should keep catalog text and images even when numeric prices are weak."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://stampauctionnetwork.com/ZA/za42023.cfm"
        return FakeResponse(AB_PHILEA_COMPACT_PAGE_HTML, url=url)

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={
                "page_url": "https://stampauctionnetwork.com/ZA/za42023.cfm",
                "sale_title": "AB Philea Online Stamp Auction - April 15-16, 2026",
                "firm_code": "ZA",
                "sale_number": "420",
                "source_auction_id": "za-420",
                "auction_id": "stampauctionnetwork:auction:za-420",
                "auctioneer_id": "stampauctionnetwork:auctioneer:za",
                "auction_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm",
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["queued_pages_this_run"] == 1
    assert result.result_summary["queued_listings_this_run"] == 2

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: (row["required_capability"], row["id"]))
    page_jobs = sorted(
        [row for row in queued_jobs if row["required_capability"] == "stampauctionnetwork page"],
        key=lambda row: row["payload"]["page_url"],
    )

    assert [row["payload"]["page_url"] for row in page_jobs] == ["https://stampauctionnetwork.com/ZA/za42024.cfm"]
    rows = _sales_listing_rows_by_source_id(pool)
    assert sorted(rows) == ["za-420-2442", "za-420-2443"]
    assert rows["za-420-2442"]["payload"]["catalog_number"] == "Facit Tj24A"
    assert rows["za-420-2442"]["title"].startswith("1 krona blue/brown")
    assert "(Image1)" not in rows["za-420-2442"]["title"]
    assert rows["za-420-2442"]["payload"]["major_group"] == "SWEDEN continued..."
    assert rows["za-420-2442"]["payload"]["sub_group"] == "Officials, perf 13 continued..."
    assert rows["za-420-2442"]["image_urls"] == ["https://stampauctionnetwork.com/assets/za420/2442-1.jpg"]
    assert rows["za-420-2443"]["image_urls"] == [
        "https://stampauctionnetwork.com/assets/za420/2443-1.jpg",
        "https://stampauctionnetwork.com/assets/za420/2443-2.jpg",
    ]
    assert float(rows["za-420-2442"]["estimate_amount"]) == 42.0
    assert rows["za-420-2442"]["seller_name"] == "AB Philea"
    assert rows["za-420-2442"]["source_query"] == "Auction"
    assert rows["za-420-2442"]["listing_status"] == "active"
    assert rows["za-420-2442"]["sold_at"] == "2026-04-15T03:00:00"
    assert rows["za-420-2443"]["payload"]["estimate_text"] == "Estimate US$ TBD"
    assert rows["za-420-2443"]["estimate_amount"] is None


def test_stamp_auction_network_page_job_keeps_compact_listings_without_prices(tmp_path):
    """Compact SAN listings should still import when price text is absent or unusable."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://stampauctionnetwork.com/ZA/za42024.cfm"
        return FakeResponse(AB_PHILEA_COMPACT_PAGE_NO_PRICE_HTML, url=url)

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={
                "page_url": "https://stampauctionnetwork.com/ZA/za42024.cfm",
                "sale_title": "AB Philea Online Stamp Auction - April 15-16, 2026",
                "firm_code": "ZA",
                "sale_number": "420",
                "source_auction_id": "za-420",
                "auction_id": "stampauctionnetwork:auction:za-420",
                "auctioneer_id": "stampauctionnetwork:auctioneer:za",
                "auction_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm",
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["queued_listings_this_run"] == 1

    rows = _sales_listing_rows_by_source_id(pool)
    assert list(rows) == ["za-420-2446"]
    assert rows["za-420-2446"]["payload"]["catalog_number"] == "Facit Tj55"
    assert rows["za-420-2446"]["title"].startswith("20 ore green")
    assert rows["za-420-2446"]["image_urls"] == ["https://stampauctionnetwork.com/assets/za420/2446-1.jpg"]
    assert rows["za-420-2446"]["payload"]["estimate_text"] == ""
    assert rows["za-420-2446"]["payload"]["price_text"] == ""
    assert rows["za-420-2446"]["estimate_amount"] is None
    assert float(rows["za-420-2446"]["price_amount"]) == -1.0


def test_stamp_auction_network_page_job_parses_compact_flat_text_when_html_rows_are_broken(tmp_path):
    """Malformed compact SAN pages should still yield listings from flat extracted text."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://stampauctionnetwork.com/ZA/za42025.cfm"
        return FakeResponse(AB_PHILEA_COMPACT_FLAT_TEXT_HTML, url=url)

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={
                "page_url": "https://stampauctionnetwork.com/ZA/za42025.cfm",
                "sale_title": "AB Philea Online Stamp Auction - April 15-16, 2026",
                "firm_code": "ZA",
                "sale_number": "420",
                "source_auction_id": "za-420",
                "auction_id": "stampauctionnetwork:auction:za-420",
                "auctioneer_id": "stampauctionnetwork:auctioneer:za",
                "auction_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm",
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["queued_listings_this_run"] == 2
    rows = _sales_listing_rows_by_source_id(pool)
    assert sorted(rows) == ["za-420-2482", "za-420-2483"]
    assert rows["za-420-2482"]["payload"]["catalog_number"] == "Facit Tj82"
    assert rows["za-420-2482"]["image_urls"] == ["https://stampauctionnetwork.com/assets/za420/2482-1.jpg"]
    assert rows["za-420-2482"]["sold_at"] == "2026-04-15T03:00:00"
    assert rows["za-420-2483"]["payload"]["estimate_text"] == "Estimate US$ TBD"
    assert rows["za-420-2483"]["estimate_amount"] is None
    assert rows["za-420-2483"]["sold_at"] == "2026-04-15T03:00:00"


def test_stamp_auction_network_page_job_ignores_support_footer_false_positive_lots(tmp_path):
    """Compact flat-text pages should ignore footer/support copy that looks like a bogus lot."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://stampauctionnetwork.com/ZA/za42024.cfm"
        return FakeResponse(AB_PHILEA_COMPACT_FLAT_TEXT_WITH_FOOTER_HTML, url=url)

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={
                "page_url": "https://stampauctionnetwork.com/ZA/za42024.cfm",
                "page_label": "Circle type with posthorn (F 40-51) Lots (2462-2481)",
                "sale_title": "AB Philea Online Stamp Auction - April 15-16, 2026",
                "firm_code": "ZA",
                "sale_number": "420",
                "source_auction_id": "za-420",
                "auction_id": "stampauctionnetwork:auction:za-420",
                "auctioneer_id": "stampauctionnetwork:auctioneer:za",
                "auction_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm",
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["queued_listings_this_run"] == 2
    rows = _sales_listing_rows_by_source_id(pool)
    assert sorted(rows) == ["za-420-2462", "za-420-2481"]


def test_stamp_auction_network_page_job_flat_text_ignores_embedded_years_when_anchor_lots_exist(tmp_path):
    """Compact flat-text pages should not split lots on years embedded in descriptions."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://stampauctionnetwork.com/ZA/za4201.cfm"
        return FakeResponse(AB_PHILEA_COMPACT_FLAT_TEXT_WITH_EMBEDDED_YEARS_HTML, url=url)

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={
                "page_url": "https://stampauctionnetwork.com/ZA/za4201.cfm",
                "sale_title": "AB Philea Online Stamp Auction - April 15-16, 2026",
                "firm_code": "ZA",
                "sale_number": "420",
                "source_auction_id": "za-420",
                "auction_id": "stampauctionnetwork:auction:za-420",
                "auctioneer_id": "stampauctionnetwork:auctioneer:za",
                "auction_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm",
            },
        )
    )

    assert result.status == "completed"
    rows = _sales_listing_rows_by_source_id(pool)
    assert sorted(rows) == ["za-420-2015", "za-420-2016"]
    assert rows["za-420-2015"]["image_urls"] == ["https://www.philea.se/objects/1688/orig/58085.jpg"]
    assert rows["za-420-2016"]["image_urls"] == ["https://www.philea.se/objects/1688/orig/54720.jpg"]
    assert "1855" in rows["za-420-2015"]["title"]
    assert "1866" in rows["za-420-2016"]["title"]


def test_stamp_auction_network_page_job_reissues_after_connection_failure(tmp_path):
    """Transient SAN page failures should reissue the job instead of raising helper errors."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        raise requests.exceptions.Timeout(f"timed out fetching {url}")

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={"page_url": "https://stampauctionnetwork.com/V/V5317.cfm"},
        )
    )

    assert result.status == "failed"
    assert result.result_summary["connection_issue"] is True
    assert result.result_summary["reissued_job_status"] == "queued"
    assert result.result_summary["reissued_priority"] == 101

    queued_jobs = pool._GetTableData(TABLE_JOBS)
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["required_capability"] == "stampauctionnetwork page"
    assert queued_jobs[0]["priority"] == 101
    assert queued_jobs[0]["metadata"]["stamp_auction_network"]["connection_retry_count"] == 1


def test_stamp_auction_network_listing_refresh_detects_seller_and_image_changes(tmp_path):
    """Page repairs should refresh SAN rows when seller or gallery content changed."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    cap = StampAuctionNetworkPageJobCap().bind_worker(worker)

    base_payload = {
        "source_listing_id": "za-420-2056",
        "firm_code": "ZA",
        "sale_number": "420",
        "source_auction_id": "za-420",
        "auction_id": "stampauctionnetwork:auction:za-420",
        "auctioneer_id": "stampauctionnetwork:auctioneer:za",
        "auction_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm",
        "lot_number": "2056",
        "title": "6 skill brownish grey on thin paper.",
        "subtitle": "SWEDEN continued... / Classics",
        "catalog_number": "Facit 3c",
        "catalog_text": "Sweden, Facit 3c or Scott 3 used, 6 skill brownish grey on thin paper.",
        "symbol_text": "used",
        "listing_status": "active",
        "sale_type": "auction",
        "listing_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm#4",
        "detail_url": "https://stampauctionnetwork.com/ZA/za4203.cfm",
        "image_url": "https://www.philea.se/objects/1688/orig/31315.jpg",
        "image_urls": ["https://www.philea.se/objects/1688/orig/31315.jpg"],
        "page_number": 4,
        "listing_position": 0,
        "price_text": "Currently...US$ 156.00",
        "price_amount": 156.0,
        "price_currency": "USD",
        "current_text": "Currently...US$ 156.00",
        "current_amount": 156.0,
        "current_currency": "USD",
        "closed_text": "Closing..Apr-15, 03:00 AM",
        "closed_at": "2026-04-15T03:00:00",
        "seller_name": "AB Philea",
        "source_url": "https://stampauctionnetwork.com/ZA/za4203.cfm",
        "sale_title": "AB Philea Online Stamp Auction - April 15-16, 2026",
        "major_group": "SWEDEN continued...",
        "sub_group": "Classics",
    }

    existing_row = cap._build_row(
        {
            **base_payload,
            "seller_name": "AB Philea Online Stamp Auction - April 15-16, 2026",
            "image_urls": [
                "https://www.philea.se/objects/1688/orig/11111.jpg",
                "https://www.philea.se/objects/1688/orig/22222.jpg",
            ],
            "image_url": "https://www.philea.se/objects/1688/orig/11111.jpg",
        }
    )

    assert cap._listing_row_needs_update(existing_row, base_payload) is True


def test_stamp_auction_network_page_job_accepts_completed_ccatalog_pages(tmp_path):
    """Completed SAN sales should parse from cCatalog pages as listing sources."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    completed_url = "https://stampauctionnetwork.com/cCatalog.cfm?SrchFirm=V&SrchSale=5311"

    def fake_request_get(url, **kwargs):
        assert url == completed_url
        return FakeResponse(CATALOG_PAGE_HTML, url=url)

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={"page_url": completed_url, "sale_title": "Kelleher Club Sale - March 1, 2026"},
        )
    )

    assert result.status == "completed"
    assert result.result_summary["queued_listings_this_run"] == 2

    queued_jobs = pool._GetTableData(TABLE_JOBS)
    image_jobs = [row for row in queued_jobs if row["required_capability"] == "stampauctionnetwork image"]
    page_jobs = [row for row in queued_jobs if row["required_capability"] == "stampauctionnetwork page"]

    assert len(image_jobs) == 2
    assert len(page_jobs) == 0
    rows = _sales_listing_rows_by_source_id(pool)
    assert sorted(rows) == ["v-5317-5140", "v-5317-5141"]
    assert rows["v-5317-5140"]["source_url"] == completed_url


def test_stamp_auction_network_page_job_parses_catalog_entries_and_queues_listing_jobs(tmp_path):
    """Catalog-like page should queue lot listing jobs plus follow-on pages."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://stampauctionnetwork.com/aCatalog3.cfm?MAJGROUP=United+States&SrchFirm=V&SrchSale=5317"
        return FakeResponse(CATALOG_PAGE_HTML, url=url)

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={
                "page_url": "https://stampauctionnetwork.com/aCatalog3.cfm?MAJGROUP=United+States&SrchFirm=V&SrchSale=5317",
                "sale_title": "Weekly Online Sales - a Division of Daniel F. Kelleher Auctions Sale - 5317",
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["queued_pages_this_run"] == 0
    assert result.result_summary["queued_listings_this_run"] == 2

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: (row["required_capability"], row["id"]))
    assert len(queued_jobs) == 2
    assert [row["required_capability"] for row in queued_jobs] == [
        "stampauctionnetwork image",
        "stampauctionnetwork image",
    ]
    assert [int(row["priority"] or 0) for row in queued_jobs] == [PRIORITY_IMAGE, PRIORITY_IMAGE]
    assert [row["payload"]["source_listing_id"] for row in queued_jobs[:2]] == ["v-5317-5140", "v-5317-5141"]
    rows = _sales_listing_rows_by_source_id(pool)
    assert rows["v-5317-5140"]["listing_url"] == "https://stampauctionnetwork.com/V/V5317.cfm#2"
    assert rows["v-5317-5140"]["search_page"] == 2
    assert rows["v-5317-5140"]["image_url"] == "https://stampauctionnetwork.com/Photos/V/5317/5140.jpg"
    assert rows["v-5317-5141"]["image_url"] == "https://stampauctionnetwork.com/Photos/V/5317/5141.jpg"


def test_stamp_auction_network_page_job_requeues_existing_listing_when_status_changed(tmp_path):
    """Existing SAN rows should be requeued when a later crawl sees a status change."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )
    pool._Insert(
        TABLE_SALES_LISTINGS,
        {
            "id": "stampauctionnetwork:v-5317-5140",
            "listing_uid": "stampauctionnetwork:v-5317-5140",
            "provider": "stampauctionnetwork",
            "source_listing_id": "v-5317-5140",
            "marketplace_site": "stampauctionnetwork.com",
            "source_category_id": "United States",
            "source_query": "Weekly Online Sales - a Division of Daniel F. Kelleher Auctions Sale - 5317",
            "listing_status": "active",
            "sale_type": "auction",
            "title": "4c Trans-Mississippi single with imprint",
            "subtitle": "United States / Air Post stamps",
            "listing_url": "https://stampauctionnetwork.com/V/V5317.cfm#2",
            "search_page": 2,
            "listing_position": 0,
            "sold_at": "",
            "price_amount": 250.0,
            "price_currency": "USD",
            "shipping_amount": None,
            "shipping_currency": "",
            "total_amount": 250.0,
            "condition_text": "**",
            "seller_name": "Weekly Online Sales - a Division of Daniel F. Kelleher Auctions",
            "location_text": "",
            "image_url": "https://stampauctionnetwork.com/Photos/V/5317/5140.jpg",
            "image_urls": ["https://stampauctionnetwork.com/Photos/V/5317/5140.jpg"],
            "image_local_paths": [],
            "source_url": "https://stampauctionnetwork.com/aCatalog3.cfm?MAJGROUP=United+States&SrchFirm=V&SrchSale=5317",
            "payload": {
                "catalog_number": "Scott #287 1898",
                "catalog_text": "Scott #287 1898, 4c Trans-Mississippi single with imprint",
                "opening_text": "Opening US$ 250.00",
                "current_text": "Currently US$ 250.00",
                "sold_text": "",
                "closed_text": "",
                "estimate_text": "",
                "sale_title": "Weekly Online Sales - a Division of Daniel F. Kelleher Auctions Sale - 5317",
                "major_group": "United States",
                "sub_group": "Air Post stamps",
            },
        },
    )

    def fake_request_get(url, **kwargs):
        assert url == "https://stampauctionnetwork.com/aCatalog3.cfm?MAJGROUP=United+States&SrchFirm=V&SrchSale=5317"
        return FakeResponse(CATALOG_PAGE_HTML, url=url)

    cap = StampAuctionNetworkPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Page",
            payload={
                "page_url": "https://stampauctionnetwork.com/aCatalog3.cfm?MAJGROUP=United+States&SrchFirm=V&SrchSale=5317",
                "sale_title": "Weekly Online Sales - a Division of Daniel F. Kelleher Auctions Sale - 5317",
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["queued_listings_this_run"] == 2

    queued_jobs = _jobs_for_capability(pool, "stampauctionnetwork image")
    assert len(queued_jobs) == 2
    assert {row["payload"]["source_listing_id"] for row in queued_jobs} == {"v-5317-5140", "v-5317-5141"}
    rows = _sales_listing_rows_by_source_id(pool)
    assert rows["v-5317-5140"]["listing_status"] == "sold"
    assert rows["v-5317-5141"]["listing_status"] == "active"


def test_stamp_auction_network_listing_job_persists_row_and_queues_image_job(tmp_path):
    """Listing job should persist a SAN row and enqueue the image job."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    cap = StampAuctionNetworkListingJobCap().bind_worker(worker)
    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Listing",
            payload={
                "source_listing_id": "v-5317-5140",
                "firm_code": "V",
                "sale_number": "5317",
                "source_auction_id": "v-5317",
                "auction_id": "stampauctionnetwork:auction:v-5317",
                "auctioneer_id": "stampauctionnetwork:auctioneer:v",
                "auction_url": "https://stampauctionnetwork.com/V/V5317.cfm",
                "lot_number": "5140",
                "title": "4c Trans-Mississippi single with imprint",
                "subtitle": "United States / Air Post stamps",
                "catalog_number": "Scott #287 1898",
                "catalog_text": "Scott #287 1898, 4c Trans-Mississippi single with imprint",
                "symbol_text": "**",
                "listing_status": "sold",
                "sale_type": "auction",
                "listing_url": "https://stampauctionnetwork.com/V/V5317.cfm#2",
                "detail_url": "https://stampauctionnetwork.com/V/v53174.cfm#Lot5140",
                "image_url": "https://stampauctionnetwork.com/Photos/V/5317/5140.jpg",
                "image_urls": ["https://stampauctionnetwork.com/Photos/V/5317/5140.jpg"],
                "page_number": 2,
                "listing_position": 0,
                "sold_text": "Sold...US$ 300.00",
                "sold_amount": 300.0,
                "sold_currency": "USD",
                "hammer_price_amount": 300.0,
                "hammer_price_currency": "USD",
                "opening_text": "Opening US$ 250.00",
                "opening_amount": 250.0,
                "opening_currency": "USD",
                "estimate_amount": 250.0,
                "estimate_currency": "USD",
                "closed_text": "Closed..Apr-12-2026, 21:00:00 EST",
                "closed_at": "2026-04-12T21:00:00",
                "seller_name": "Weekly Online Sales - a Division of Daniel F. Kelleher Auctions",
                "source_url": "https://stampauctionnetwork.com/aCatalog3.cfm?MAJGROUP=United+States&SrchFirm=V&SrchSale=5317",
                "sale_title": "Weekly Online Sales - a Division of Daniel F. Kelleher Auctions Sale - 5317",
                "major_group": "United States",
                "sub_group": "Air Post stamps",
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["image_job_queued"] is True

    rows = pool._GetTableData(
        TABLE_SALES_LISTINGS,
        "stampauctionnetwork:v-5317-5140",
        table_schema=sales_listings_table_schema(),
    )
    assert len(rows) == 1
    assert rows[0]["provider"] == "stampauctionnetwork"
    assert rows[0]["source_listing_id"] == "v-5317-5140"
    assert rows[0]["auction_id"] == "stampauctionnetwork:auction:v-5317"
    assert rows[0]["auctioneer_id"] == "stampauctionnetwork:auctioneer:v"
    assert rows[0]["lot_number"] == "5140"
    assert rows[0]["title"] == "4c Trans-Mississippi single with imprint"
    assert float(rows[0]["price_amount"]) == 300.0
    assert float(rows[0]["estimate_amount"]) == 250.0
    assert float(rows[0]["hammer_price_amount"]) == 300.0

    queued_jobs = pool._GetTableData(TABLE_JOBS)
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["required_capability"] == "stampauctionnetwork image"
    assert queued_jobs[0]["payload"]["source_listing_id"] == "v-5317-5140"
    assert int(queued_jobs[0]["priority"] or 0) == PRIORITY_IMAGE
    assert int(queued_jobs[0]["priority"] or 0) > PRIORITY_PAGE_NEW_AUCTION


def test_stamp_auction_network_listing_job_skips_image_queue_when_no_known_images(tmp_path):
    """Listings without image candidates should persist without queuing image jobs."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    cap = StampAuctionNetworkListingJobCap().bind_worker(worker)
    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Listing",
            payload={
                "source_listing_id": "nz-30-201",
                "firm_code": "NZ",
                "sale_number": "30",
                "source_auction_id": "nz-30",
                "auction_id": "stampauctionnetwork:auction:nz-30",
                "auctioneer_id": "stampauctionnetwork:auctioneer:nz",
                "auction_url": "https://stampauctionnetwork.com/NZ/NZ30.cfm",
                "lot_number": "201",
                "title": "Early Collection NZ Territory era",
                "catalog_text": "1901/1930's Early Collection NZ Territory era",
                "listing_status": "active",
                "sale_type": "auction",
                "listing_url": "https://stampauctionnetwork.com/NZ/NZ30.cfm#12",
                "detail_url": "https://stampauctionnetwork.com/NZ/nz3011.cfm",
                "image_url": "",
                "image_urls": [],
                "page_number": 12,
                "listing_position": 0,
                "price_text": "",
                "price_amount": -1,
                "price_currency": "",
                "seller_name": "Mowbray Collectables",
                "source_url": "https://stampauctionnetwork.com/NZ/nz3011.cfm",
                "sale_title": "Mowbray Collectables Public Auction - 30",
                "major_group": "New Zealand",
                "sub_group": "Collections",
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["image_job_queued"] is False
    assert result.result_summary["image_job_status"] == "no_known_images"
    assert _jobs_for_capability(pool, "stampauctionnetwork image") == []


def test_stamp_auction_network_listing_job_repairs_legacy_sales_listings_schema(tmp_path):
    """Legacy sales_listings tables should gain new SAN columns before listing inserts."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    pool._Query(
        """
        CREATE TABLE sales_listings (
            id TEXT PRIMARY KEY,
            listing_uid TEXT,
            provider TEXT,
            source_listing_id TEXT
        )
        """
    )

    cap = StampAuctionNetworkListingJobCap().bind_worker(worker)
    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Listing",
            payload={
                "source_listing_id": "v-5317-5140",
                "firm_code": "V",
                "sale_number": "5317",
                "source_auction_id": "v-5317",
                "auction_id": "stampauctionnetwork:auction:v-5317",
                "auctioneer_id": "stampauctionnetwork:auctioneer:v",
                "auction_url": "https://stampauctionnetwork.com/V/V5317.cfm",
                "lot_number": "5140",
                "title": "4c Trans-Mississippi single with imprint",
                "subtitle": "United States / Air Post stamps",
                "catalog_number": "Scott #287 1898",
                "catalog_text": "Scott #287 1898, 4c Trans-Mississippi single with imprint",
                "symbol_text": "**",
                "listing_status": "sold",
                "sale_type": "auction",
                "listing_url": "https://stampauctionnetwork.com/V/V5317.cfm#2",
                "detail_url": "https://stampauctionnetwork.com/V/v53174.cfm#Lot5140",
                "image_url": "https://stampauctionnetwork.com/Photos/V/5317/5140.jpg",
                "image_urls": ["https://stampauctionnetwork.com/Photos/V/5317/5140.jpg"],
                "page_number": 2,
                "listing_position": 0,
                "sold_text": "Sold...US$ 300.00",
                "sold_amount": 300.0,
                "sold_currency": "USD",
                "hammer_price_amount": 300.0,
                "hammer_price_currency": "USD",
                "opening_text": "Opening US$ 250.00",
                "opening_amount": 250.0,
                "opening_currency": "USD",
                "estimate_amount": 250.0,
                "estimate_currency": "USD",
                "closed_text": "Closed..Apr-12-2026, 21:00:00 EST",
                "closed_at": "2026-04-12T21:00:00",
                "seller_name": "Weekly Online Sales - a Division of Daniel F. Kelleher Auctions",
                "source_url": "https://stampauctionnetwork.com/aCatalog3.cfm?MAJGROUP=United+States&SrchFirm=V&SrchSale=5317",
                "sale_title": "Weekly Online Sales - a Division of Daniel F. Kelleher Auctions Sale - 5317",
                "major_group": "United States",
                "sub_group": "Air Post stamps",
            },
        )
    )

    assert result.status == "completed"
    columns = {row[1] for row in pool._Query("PRAGMA table_info('sales_listings')")}
    assert {"auctioneer_id", "auction_id", "lot_number", "estimate_amount", "hammer_price_amount"}.issubset(columns)

    rows = pool._GetTableData(
        TABLE_SALES_LISTINGS,
        "stampauctionnetwork:v-5317-5140",
        table_schema=sales_listings_table_schema(),
    )
    assert len(rows) == 1
    assert rows[0]["auctioneer_id"] == "stampauctionnetwork:auctioneer:v"
    assert rows[0]["auction_id"] == "stampauctionnetwork:auction:v-5317"


def test_stamp_auction_network_listing_job_updates_existing_row_when_status_changes(tmp_path):
    """Existing SAN rows should be updated when the lot moves from active to sold."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )
    pool._Insert(
        TABLE_SALES_LISTINGS,
        {
            "id": "stampauctionnetwork:v-5317-5140",
            "listing_uid": "stampauctionnetwork:v-5317-5140",
            "provider": "stampauctionnetwork",
            "source_listing_id": "v-5317-5140",
            "marketplace_site": "stampauctionnetwork.com",
            "source_category_id": "United States",
            "source_query": "Weekly Online Sales - a Division of Daniel F. Kelleher Auctions Sale - 5317",
            "listing_status": "active",
            "sale_type": "auction",
            "title": "4c Trans-Mississippi single with imprint",
            "subtitle": "United States / Air Post stamps",
            "listing_url": "https://stampauctionnetwork.com/V/V5317.cfm#2",
            "search_page": 2,
            "listing_position": 0,
            "sold_at": "",
            "price_amount": 250.0,
            "price_currency": "USD",
            "shipping_amount": None,
            "shipping_currency": "",
            "total_amount": 250.0,
            "condition_text": "**",
            "seller_name": "Weekly Online Sales - a Division of Daniel F. Kelleher Auctions",
            "location_text": "",
            "image_url": "https://stampauctionnetwork.com/Photos/V/5317/5140.jpg",
            "image_urls": ["https://stampauctionnetwork.com/Photos/V/5317/5140.jpg"],
            "image_local_paths": [],
            "source_url": "https://stampauctionnetwork.com/aCatalog3.cfm?MAJGROUP=United+States&SrchFirm=V&SrchSale=5317",
            "payload": {
                "catalog_number": "Scott #287 1898",
                "catalog_text": "Scott #287 1898, 4c Trans-Mississippi single with imprint",
                "opening_text": "Opening US$ 250.00",
                "current_text": "Currently US$ 250.00",
                "sold_text": "",
                "closed_text": "",
                "estimate_text": "",
                "sale_title": "Weekly Online Sales - a Division of Daniel F. Kelleher Auctions Sale - 5317",
                "major_group": "United States",
                "sub_group": "Air Post stamps",
            },
        },
    )

    cap = StampAuctionNetworkListingJobCap().bind_worker(worker)
    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Listing",
            payload={
                "source_listing_id": "v-5317-5140",
                "firm_code": "V",
                "sale_number": "5317",
                "lot_number": "5140",
                "title": "4c Trans-Mississippi single with imprint",
                "subtitle": "United States / Air Post stamps",
                "catalog_number": "Scott #287 1898",
                "catalog_text": "Scott #287 1898, 4c Trans-Mississippi single with imprint",
                "symbol_text": "**",
                "listing_status": "sold",
                "sale_type": "auction",
                "listing_url": "https://stampauctionnetwork.com/V/V5317.cfm#2",
                "image_url": "https://stampauctionnetwork.com/Photos/V/5317/5140.jpg",
                "image_urls": ["https://stampauctionnetwork.com/Photos/V/5317/5140.jpg"],
                "page_number": 2,
                "listing_position": 0,
                "sold_text": "Sold...US$ 300.00",
                "sold_amount": 300.0,
                "sold_currency": "USD",
                "opening_text": "Opening US$ 250.00",
                "opening_amount": 250.0,
                "opening_currency": "USD",
                "closed_text": "Closed..Apr-12-2026, 21:00:00 EST",
                "closed_at": "2026-04-12T21:00:00",
                "seller_name": "Weekly Online Sales - a Division of Daniel F. Kelleher Auctions",
                "source_url": "https://stampauctionnetwork.com/aCatalog3.cfm?MAJGROUP=United+States&SrchFirm=V&SrchSale=5317",
                "sale_title": "Weekly Online Sales - a Division of Daniel F. Kelleher Auctions Sale - 5317",
                "major_group": "United States",
                "sub_group": "Air Post stamps",
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["image_job_queued"] is True

    rows = pool._GetTableData(
        TABLE_SALES_LISTINGS,
        "stampauctionnetwork:v-5317-5140",
        table_schema=sales_listings_table_schema(),
    )
    assert len(rows) == 1
    assert rows[0]["listing_status"] == "sold"
    assert rows[0]["sold_at"] == "2026-04-12T21:00:00"
    assert float(rows[0]["price_amount"]) == 300.0
    assert rows[0]["payload"]["sold_text"] == "Sold...US$ 300.00"


def test_stamp_auction_network_image_job_downloads_image_and_updates_listing(tmp_path):
    """Image job should fetch detail/image content and backfill local asset paths."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )
    pool._Insert(
        TABLE_SALES_LISTINGS,
        {
            "id": "stampauctionnetwork:v-5317-5140",
            "listing_uid": "stampauctionnetwork:v-5317-5140",
            "provider": "stampauctionnetwork",
            "source_listing_id": "v-5317-5140",
            "marketplace_site": "stampauctionnetwork.com",
            "source_category_id": "United States",
            "source_query": "Weekly Online Sales - a Division of Daniel F. Kelleher Auctions Sale - 5317",
            "listing_status": "sold",
            "sale_type": "auction",
            "title": "4c Trans-Mississippi single with imprint",
            "subtitle": "United States / Air Post stamps",
            "listing_url": "https://stampauctionnetwork.com/V/V5317.cfm#2",
            "search_page": 2,
            "listing_position": 0,
            "sold_at": "2026-04-12T21:00:00",
            "price_amount": 300.0,
            "price_currency": "USD",
            "shipping_amount": None,
            "shipping_currency": "",
            "total_amount": 300.0,
            "condition_text": "**",
            "seller_name": "Weekly Online Sales - a Division of Daniel F. Kelleher Auctions",
            "location_text": "",
            "image_url": "https://stampauctionnetwork.com/Photos/V/5317/5140.jpg",
            "image_urls": ["https://stampauctionnetwork.com/Photos/V/5317/5140.jpg"],
            "image_local_paths": [],
            "source_url": "https://stampauctionnetwork.com/aCatalog3.cfm?MAJGROUP=United+States&SrchFirm=V&SrchSale=5317",
            "payload": {},
        },
    )

    def fake_request_get(url, **kwargs):
        if url == "https://stampauctionnetwork.com/V/v53174.cfm#Lot5140":
            return FakeResponse(DETAIL_PAGE_HTML, url=url)
        if url == "https://stampauctionnetwork.com/Photos/V/5317/5140.jpg":
            return FakeResponse("", url=url, content=b"fake-jpg", headers={"Content-Type": "image/jpeg"})
        raise AssertionError(url)

    cap = StampAuctionNetworkImageJobCap(
        request_get=fake_request_get,
        media_root=str(tmp_path / "media"),
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Image",
            payload={
                "source_listing_id": "v-5317-5140",
                "listing_url": "https://stampauctionnetwork.com/V/V5317.cfm#2",
                "detail_url": "https://stampauctionnetwork.com/V/v53174.cfm#Lot5140",
                "image_url": "https://stampauctionnetwork.com/Photos/V/5317/5140.jpg",
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["image_urls"] == ["https://stampauctionnetwork.com/Photos/V/5317/5140.jpg"]
    local_path = Path(result.result_summary["image_local_paths"][0])
    assert local_path.exists()
    assert local_path.read_bytes() == b"fake-jpg"

    rows = pool._GetTableData(
        TABLE_SALES_LISTINGS,
        "stampauctionnetwork:v-5317-5140",
        table_schema=sales_listings_table_schema(),
    )
    assert len(rows) == 1
    assert rows[0]["image_local_paths"] == [str(local_path)]
    assert rows[0]["title"] == "4c Trans-Mississippi single with imprint"


def test_stamp_auction_network_image_job_completes_when_no_images_are_found(tmp_path):
    """No-image SAN detail pages should complete as terminal skips instead of failed retries."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    detail_url = "https://stampauctionnetwork.com/NZ/nz3011.cfm"

    ensure_dispatcher_tables(
        pool,
        [TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )
    pool._Insert(
        TABLE_SALES_LISTINGS,
        {
            "id": "stampauctionnetwork:nz-30-201",
            "listing_uid": "stampauctionnetwork:nz-30-201",
            "provider": "stampauctionnetwork",
            "source_listing_id": "nz-30-201",
            "marketplace_site": "stampauctionnetwork.com",
            "source_category_id": "New Zealand",
            "source_query": "Auction",
            "listing_status": "active",
            "sale_type": "auction",
            "title": "Early Collection NZ Territory era",
            "subtitle": "",
            "listing_url": "https://stampauctionnetwork.com/NZ/NZ30.cfm#12",
            "search_page": 12,
            "listing_position": 0,
            "sold_at": "",
            "price_amount": -1.0,
            "price_currency": "",
            "shipping_amount": None,
            "shipping_currency": "",
            "total_amount": -1.0,
            "condition_text": "",
            "seller_name": "Mowbray Collectables",
            "location_text": "",
            "image_url": "",
            "image_urls": [],
            "image_local_paths": [],
            "source_url": detail_url,
            "payload": {},
        },
    )

    def fake_request_get(url, **kwargs):
        if url == detail_url:
            return FakeResponse("<html><body><div>No images here</div></body></html>", url=url, headers={"Content-Type": "text/html"})
        raise AssertionError(url)

    cap = StampAuctionNetworkImageJobCap(
        request_get=fake_request_get,
        media_root=str(tmp_path / "media"),
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Image",
            payload={
                "source_listing_id": "nz-30-201",
                "listing_url": "https://stampauctionnetwork.com/NZ/NZ30.cfm#12",
                "detail_url": detail_url,
                "image_url": "",
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["skipped_no_images"] is True
    assert result.result_summary["image_local_paths"] == []


def test_stamp_auction_network_image_job_ignores_page_wide_images_for_image_less_lot(tmp_path):
    """Multi-lot SAN detail pages should not donate unrelated page images to an image-less lot."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    detail_url = "https://stampauctionnetwork.com/GB/gb342114.cfm"

    ensure_dispatcher_tables(
        pool,
        [TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )
    pool._Insert(
        TABLE_SALES_LISTINGS,
        {
            "id": "stampauctionnetwork:gb-342-5729",
            "listing_uid": "stampauctionnetwork:gb-342-5729",
            "provider": "stampauctionnetwork",
            "source_listing_id": "gb-342-5729",
            "marketplace_site": "stampauctionnetwork.com",
            "source_category_id": "Germany",
            "source_query": "Auction",
            "listing_status": "active",
            "sale_type": "auction",
            "title": "1984-90, Jahrbucher kpl. in Schmuckbox mit DDR Emblem",
            "subtitle": "",
            "listing_url": "https://stampauctionnetwork.com/GB/GB342.cfm#114",
            "search_page": 114,
            "listing_position": 0,
            "sold_at": "",
            "price_amount": 50.0,
            "price_currency": "EUR",
            "shipping_amount": None,
            "shipping_currency": "",
            "total_amount": 50.0,
            "condition_text": "",
            "seller_name": "Georg Buhler Nachfolger Briefmarken-Auktionen GmbH",
            "location_text": "",
            "image_url": "https://www.briefmarken-buehler.de/fotos/59004.jpg",
            "image_urls": [
                "https://www.briefmarken-buehler.de/fotos/59004.jpg",
                "https://www.briefmarken-buehler.de/fotos/65990.jpg",
            ],
            "image_local_paths": [],
            "source_url": detail_url,
            "payload": {
                "detail_url": detail_url,
                "raw_block_html": """
                    <TR VALIGN=TOP>
                    <TD WIDTH="5%">5729</TD>
                    <TD WIDTH="13%"></TD>
                    <TD WIDTH="55%" bgcolor="#DDDDDD">
                    <A NAME = "Lot5729">
                    1984-90, Jahrbucher kpl. in Schmuckbox mit DDR Emblem
                    </TD>
                    <TD VALIGN=BOTTOM ALIGN=RIGHT WIDTH="13%">
                    Start Bid &#8364;50
                    <br><br>
                    <b><font color=blue>
                    <br>Closing..Apr-17, 06:00 AM</TD>
                    </TR>
                """,
            },
        },
    )

    def fake_request_get(url, **kwargs):
        if url == detail_url:
            return FakeResponse(
                """
                <html><body>
                <table>
                  <tr valign="top">
                    <td width="5%">4161</td>
                    <td width="13%">WZd31-33</td>
                    <td width="55%" bgcolor="#DDDDDD">
                      <a name="Lot4161"></a>
                      <a href="https://www.briefmarken-buehler.de/fotos/59004.jpg" title="Lot 4161" class="MagicZoomPlus">
                        <img align="left" src="https://www.briefmarken-buehler.de/fotos/59004.jpg" width="300p" alt="image">
                      </a>
                    </td>
                  </tr>
                  <tr valign="top">
                    <td width="5%">4162</td>
                    <td width="13%">WZD118</td>
                    <td width="55%" bgcolor="#DDDDDD">
                      <a name="Lot4162"></a>
                      <a href="https://www.briefmarken-buehler.de/fotos/65990.jpg" title="Lot 4162" class="MagicZoomPlus">
                        <img align="left" src="https://www.briefmarken-buehler.de/fotos/65990.jpg" width="300p" alt="image">
                      </a>
                    </td>
                  </tr>
                  <tr valign="top">
                    <td width="5%">5729</td>
                    <td width="13%"></td>
                    <td width="55%" bgcolor="#DDDDDD">
                      <a name="Lot5729"></a>
                      1984-90, Jahrbucher kpl. in Schmuckbox mit DDR Emblem
                    </td>
                  </tr>
                </table>
                </body></html>
                """,
                url=url,
                headers={"Content-Type": "text/html"},
            )
        raise AssertionError(url)

    cap = StampAuctionNetworkImageJobCap(
        request_get=fake_request_get,
        media_root=str(tmp_path / "media"),
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Image",
            payload={
                "source_listing_id": "gb-342-5729",
                "listing_url": "https://stampauctionnetwork.com/GB/GB342.cfm#114",
                "detail_url": detail_url,
                "image_url": "https://www.briefmarken-buehler.de/fotos/59004.jpg",
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["skipped_no_images"] is True
    assert result.result_summary["image_urls"] == []


def test_stamp_auction_network_image_job_reuses_cached_detail_page_until_refreshed(tmp_path):
    """Image jobs should use the shared page cache for detail pages unless forced to refresh."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    request_urls: list[str] = []
    detail_url = "https://stampauctionnetwork.com/V/v53174.cfm#Lot5140"
    image_url = "https://stampauctionnetwork.com/Photos/V/5317/5140.jpg"

    def fake_request_get(url, **kwargs):
        request_urls.append(url)
        if url == detail_url:
            return FakeResponse(DETAIL_PAGE_HTML, url=url, headers={"Content-Type": "text/html"})
        if url == image_url:
            return FakeResponse("", url=url, content=b"fake-jpg", headers={"Content-Type": "image/jpeg"})
        raise AssertionError(url)

    ensure_dispatcher_tables(
        pool,
        [TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )
    pool._Insert(
        TABLE_SALES_LISTINGS,
        {
            "id": "stampauctionnetwork:v-5317-5140",
            "listing_uid": "stampauctionnetwork:v-5317-5140",
            "provider": "stampauctionnetwork",
            "source_listing_id": "v-5317-5140",
            "marketplace_site": "stampauctionnetwork.com",
            "source_category_id": "United States",
            "source_query": "Auction",
            "listing_status": "sold",
            "sale_type": "auction",
            "title": "4c Trans-Mississippi single with imprint",
            "subtitle": "United States / Air Post stamps",
            "listing_url": "https://stampauctionnetwork.com/V/V5317.cfm#2",
            "search_page": 2,
            "listing_position": 0,
            "sold_at": "2026-04-12T21:00:00",
            "price_amount": 300.0,
            "price_currency": "USD",
            "shipping_amount": None,
            "shipping_currency": "",
            "total_amount": 300.0,
            "condition_text": "**",
            "seller_name": "Daniel F. Kelleher Auctions",
            "location_text": "",
            "image_url": image_url,
            "image_urls": [image_url],
            "image_local_paths": [],
            "source_url": "https://stampauctionnetwork.com/aCatalog3.cfm?MAJGROUP=United+States&SrchFirm=V&SrchSale=5317",
            "payload": {},
        },
    )

    cap = StampAuctionNetworkImageJobCap(request_get=fake_request_get, media_root=str(tmp_path / "media")).bind_worker(worker)

    first = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Image",
            payload={
                "source_listing_id": "v-5317-5140",
                "listing_url": "https://stampauctionnetwork.com/V/V5317.cfm#2",
                "detail_url": detail_url,
                "image_url": image_url,
            },
        )
    )
    second = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Image",
            payload={
                "source_listing_id": "v-5317-5140",
                "listing_url": "https://stampauctionnetwork.com/V/V5317.cfm#2",
                "detail_url": detail_url,
                "image_url": image_url,
            },
        )
    )
    third = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Image",
            payload={
                "source_listing_id": "v-5317-5140",
                "listing_url": "https://stampauctionnetwork.com/V/V5317.cfm#2",
                "detail_url": detail_url,
                "image_url": image_url,
                "refresh_item": True,
            },
        )
    )

    assert first.status == "completed"
    assert second.status == "completed"
    assert third.status == "completed"
    assert request_urls.count(detail_url) == 2
    assert second.result_summary["source_listing_id"] == "v-5317-5140"
    assert first.result_summary["image_urls"] == [image_url]
    assert second.result_summary["image_urls"] == [image_url]
    assert third.result_summary["image_urls"] == [image_url]

    cached_rows = _web_page_rows_by_source_url(pool)
    cached_detail_url = "https://stampauctionnetwork.com/V/v53174.cfm"
    assert cached_detail_url in cached_rows
    assert cached_rows[cached_detail_url]["page_kind"] == "listing_detail"
    assert cached_rows[cached_detail_url]["content_type"] == "text/html"


def test_stamp_auction_network_image_job_reuses_existing_local_image_without_redownload(tmp_path):
    """Image jobs should reuse existing local files and skip the image HTTP fetch."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    detail_url = "https://stampauctionnetwork.com/V/v53174.cfm#Lot5140"
    image_url = "https://stampauctionnetwork.com/Photos/V/5317/5140.jpg"
    media_root = tmp_path / "media"
    existing_local_path = media_root / "sales" / "v-5317-5140" / "01.jpg"
    existing_local_path.parent.mkdir(parents=True, exist_ok=True)
    existing_local_path.write_bytes(b"already-have-it")
    request_urls: list[str] = []

    def fake_request_get(url, **kwargs):
        request_urls.append(url)
        if url == detail_url:
            return FakeResponse(DETAIL_PAGE_HTML, url=url, headers={"Content-Type": "text/html"})
        raise AssertionError(f"Image URL should not be downloaded again: {url}")

    ensure_dispatcher_tables(
        pool,
        [TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )
    pool._Insert(
        TABLE_SALES_LISTINGS,
        {
            "id": "stampauctionnetwork:v-5317-5140",
            "listing_uid": "stampauctionnetwork:v-5317-5140",
            "provider": "stampauctionnetwork",
            "source_listing_id": "v-5317-5140",
            "marketplace_site": "stampauctionnetwork.com",
            "source_category_id": "United States",
            "source_query": "Auction",
            "listing_status": "sold",
            "sale_type": "auction",
            "title": "4c Trans-Mississippi single with imprint",
            "subtitle": "United States / Air Post stamps",
            "listing_url": "https://stampauctionnetwork.com/V/V5317.cfm#2",
            "search_page": 2,
            "listing_position": 0,
            "sold_at": "2026-04-12T21:00:00",
            "price_amount": 300.0,
            "price_currency": "USD",
            "shipping_amount": None,
            "shipping_currency": "",
            "total_amount": 300.0,
            "condition_text": "**",
            "seller_name": "Daniel F. Kelleher Auctions",
            "location_text": "",
            "image_url": image_url,
            "image_urls": [image_url],
            "image_local_paths": [str(existing_local_path)],
            "source_url": "https://stampauctionnetwork.com/aCatalog3.cfm?MAJGROUP=United+States&SrchFirm=V&SrchSale=5317",
            "payload": {},
        },
    )

    cap = StampAuctionNetworkImageJobCap(
        request_get=fake_request_get,
        media_root=str(media_root),
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Image",
            payload={
                "source_listing_id": "v-5317-5140",
                "listing_url": "https://stampauctionnetwork.com/V/V5317.cfm#2",
                "detail_url": detail_url,
                "image_url": image_url,
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["image_local_paths"] == [str(existing_local_path)]
    assert existing_local_path.read_bytes() == b"already-have-it"
    assert request_urls == [detail_url]

    rows = pool._GetTableData(
        TABLE_SALES_LISTINGS,
        "stampauctionnetwork:v-5317-5140",
        table_schema=sales_listings_table_schema(),
    )
    assert len(rows) == 1
    assert rows[0]["image_local_paths"] == [str(existing_local_path)]


def test_stamp_auction_network_image_job_redownloads_when_only_stale_slot_file_exists(tmp_path):
    """Image jobs should not trust a guessed cache slot when the row has no explicit local-path binding."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    detail_url = "https://stampauctionnetwork.com/V/v53174.cfm#Lot5140"
    image_url = "https://stampauctionnetwork.com/Photos/V/5317/5140.jpg"
    media_root = tmp_path / "media"
    stale_local_path = media_root / "sales" / "v-5317-5140" / "01.jpg"
    stale_local_path.parent.mkdir(parents=True, exist_ok=True)
    stale_local_path.write_bytes(b"stale-image")
    request_urls: list[str] = []

    def fake_request_get(url, **kwargs):
        request_urls.append(url)
        if url == detail_url:
            return FakeResponse(DETAIL_PAGE_HTML, url=url, headers={"Content-Type": "text/html"})
        if url == image_url:
            return FakeResponse("", url=url, content=b"fresh-image", headers={"Content-Type": "image/jpeg"})
        raise AssertionError(url)

    ensure_dispatcher_tables(
        pool,
        [TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )
    pool._Insert(
        TABLE_SALES_LISTINGS,
        {
            "id": "stampauctionnetwork:v-5317-5140",
            "listing_uid": "stampauctionnetwork:v-5317-5140",
            "provider": "stampauctionnetwork",
            "source_listing_id": "v-5317-5140",
            "marketplace_site": "stampauctionnetwork.com",
            "source_category_id": "United States",
            "source_query": "Auction",
            "listing_status": "sold",
            "sale_type": "auction",
            "title": "4c Trans-Mississippi single with imprint",
            "subtitle": "United States / Air Post stamps",
            "listing_url": "https://stampauctionnetwork.com/V/V5317.cfm#2",
            "search_page": 2,
            "listing_position": 0,
            "sold_at": "2026-04-12T21:00:00",
            "price_amount": 300.0,
            "price_currency": "USD",
            "shipping_amount": None,
            "shipping_currency": "",
            "total_amount": 300.0,
            "condition_text": "**",
            "seller_name": "Daniel F. Kelleher Auctions",
            "location_text": "",
            "image_url": image_url,
            "image_urls": [image_url],
            "image_local_paths": [],
            "source_url": "https://stampauctionnetwork.com/aCatalog3.cfm?MAJGROUP=United+States&SrchFirm=V&SrchSale=5317",
            "payload": {},
        },
    )

    cap = StampAuctionNetworkImageJobCap(
        request_get=fake_request_get,
        media_root=str(media_root),
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Image",
            payload={
                "source_listing_id": "v-5317-5140",
                "listing_url": "https://stampauctionnetwork.com/V/V5317.cfm#2",
                "detail_url": detail_url,
                "image_url": image_url,
            },
        )
    )

    assert result.status == "completed"
    assert request_urls == [detail_url, image_url]
    assert stale_local_path.read_bytes() == b"fresh-image"
    assert result.result_summary["image_local_paths"] == [str(stale_local_path)]


def test_stamp_auction_network_image_job_keeps_partial_downloads_when_one_asset_404s(tmp_path):
    """Image jobs should persist downloaded images even if a later gallery asset 404s."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    detail_url = "https://stampauctionnetwork.com/ZA/za420112.cfm"
    good_image_url = "https://www.philea.se/objects/1688/orig/84454.jpg"
    broken_image_url = "https://www.philea.se/objects/1688/orig/84454-10.jpg"

    ensure_dispatcher_tables(
        pool,
        [TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )
    pool._Insert(
        TABLE_SALES_LISTINGS,
        {
            "id": "stampauctionnetwork:za-420-4231",
            "listing_uid": "stampauctionnetwork:za-420-4231",
            "provider": "stampauctionnetwork",
            "source_listing_id": "za-420-4231",
            "marketplace_site": "stampauctionnetwork.com",
            "source_category_id": "SWEDEN",
            "source_query": "Auction",
            "listing_status": "active",
            "sale_type": "auction",
            "title": "AB Philea lot with one broken extra image",
            "subtitle": "",
            "listing_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm#113",
            "search_page": 113,
            "listing_position": 0,
            "sold_at": "",
            "price_amount": 32.0,
            "price_currency": "USD",
            "shipping_amount": None,
            "shipping_currency": "",
            "total_amount": 32.0,
            "condition_text": "",
            "seller_name": "AB Philea",
            "location_text": "",
            "image_url": good_image_url,
            "image_urls": [good_image_url, broken_image_url],
            "image_local_paths": [],
            "source_url": detail_url,
            "payload": {},
        },
    )

    def fake_request_get(url, **kwargs):
        if url == detail_url:
            return FakeResponse(DETAIL_PAGE_WITH_BROKEN_EXTRA_IMAGE_HTML, url=url, headers={"Content-Type": "text/html"})
        if url == good_image_url:
            return FakeResponse("", url=url, content=b"good-image", headers={"Content-Type": "image/jpeg"})
        if url == broken_image_url:
            return FakeResponse("missing", url=url, status_code=404, headers={"Content-Type": "text/html"})
        raise AssertionError(url)

    cap = StampAuctionNetworkImageJobCap(
        request_get=fake_request_get,
        media_root=str(tmp_path / "media"),
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Image",
            payload={
                "source_listing_id": "za-420-4231",
                "listing_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm#113",
                "detail_url": detail_url,
                "image_url": good_image_url,
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["image_urls"] == [good_image_url, broken_image_url]
    assert len(result.result_summary["image_local_paths"]) == 1
    local_path = Path(result.result_summary["image_local_paths"][0])
    assert local_path.exists()
    assert local_path.read_bytes() == b"good-image"

    rows = pool._GetTableData(
        TABLE_SALES_LISTINGS,
        "stampauctionnetwork:za-420-4231",
        table_schema=sales_listings_table_schema(),
    )
    assert len(rows) == 1
    assert rows[0]["image_local_paths"] == [str(local_path)]
    assert rows[0]["image_urls"] == [good_image_url, broken_image_url]


def test_stamp_auction_network_image_job_keeps_row_images_for_same_source_page(tmp_path):
    """Compact SAN image jobs should not replace lot images with the whole source-page gallery."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    detail_url = "https://stampauctionnetwork.com/ZA/za4203.cfm"
    correct_image_url = "https://www.philea.se/objects/1688/orig/56809.jpg"
    wrong_image_url = "https://www.philea.se/objects/1688/orig/99999.jpg"
    page_gallery_html = f"""
    <html>
      <head><title>SWEDEN continued...</title></head>
      <body>
        <img src="{wrong_image_url}" />
        <img src="{correct_image_url}" />
      </body>
    </html>
    """

    def fake_request_get(url, **kwargs):
        if url == detail_url:
            return FakeResponse(page_gallery_html, url=url, headers={"Content-Type": "text/html"})
        if url == correct_image_url:
            return FakeResponse("", url=url, content=b"right-image", headers={"Content-Type": "image/jpeg"})
        raise AssertionError(url)

    ensure_dispatcher_tables(
        pool,
        [TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )
    pool._Insert(
        TABLE_SALES_LISTINGS,
        {
            "id": "stampauctionnetwork:za-420-2056",
            "listing_uid": "stampauctionnetwork:za-420-2056",
            "provider": "stampauctionnetwork",
            "source_listing_id": "za-420-2056",
            "marketplace_site": "stampauctionnetwork.com",
            "source_category_id": "SWEDEN continued...",
            "source_query": "Auction",
            "listing_status": "active",
            "sale_type": "auction",
            "title": "Sweden, Facit 3c or Scott 3 used, 6 skill brownish grey on thin paper.",
            "subtitle": "SWEDEN continued... / Classics",
            "listing_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm#4",
            "search_page": 4,
            "listing_position": 0,
            "sold_at": "2026-04-15T03:00:00",
            "price_amount": 156.0,
            "price_currency": "USD",
            "shipping_amount": None,
            "shipping_currency": "",
            "total_amount": 156.0,
            "condition_text": "used",
            "seller_name": "AB Philea",
            "location_text": "",
            "image_url": correct_image_url,
            "image_urls": [correct_image_url],
            "image_local_paths": [],
            "source_url": detail_url,
            "payload": {
                "detail_url": detail_url,
                "catalog_text": "Sweden, Facit 3c or Scott 3 used, 6 skill brownish grey on thin paper.",
                "raw_block_text": "2056 Image: Sweden, Facit 3c or Scott 3 used. (Image1)",
            },
        },
    )

    cap = StampAuctionNetworkImageJobCap(
        request_get=fake_request_get,
        media_root=str(tmp_path / "media"),
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampAuctionNetwork Image",
            payload={
                "source_listing_id": "za-420-2056",
                "listing_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm#4",
                "detail_url": detail_url,
                "image_url": correct_image_url,
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["image_urls"] == [correct_image_url]

    rows = pool._GetTableData(
        TABLE_SALES_LISTINGS,
        "stampauctionnetwork:za-420-2056",
        table_schema=sales_listings_table_schema(),
    )
    assert len(rows) == 1
    assert rows[0]["title"] == "Sweden, Facit 3c or Scott 3 used, 6 skill brownish grey on thin paper."
    assert rows[0]["image_url"] == correct_image_url
    assert rows[0]["image_urls"] == [correct_image_url]
