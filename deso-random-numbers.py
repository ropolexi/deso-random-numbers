import requests
import json
import time
from deso_sdk import DeSoDexClient
from deso_sdk  import base58_check_encode
from pprint import pprint
import datetime
import re
import logging
import random
logging.basicConfig(format='%(asctime)s-%(levelname)s:[%(lineno)d]%(message)s', level=logging.DEBUG)

REMOTE_API = False
HAS_LOCAL_NODE_WITH_INDEXING = False
HAS_LOCAL_NODE_WITHOUT_INDEXING = True


BASE_URL = "https://node.deso.org"

seed_phrase_or_hex="" #dont share this
NOTIFICATION_UPDATE_INTERVEL = 30 #in seconds

api_url = BASE_URL+"/api/"
local_url= "http://localhost:17001"+"/api/"


# Global variables for thread control
stop_flag = True
calculation_thread = None
app_close=False
nodes={}
height=0
if REMOTE_API:
    HAS_LOCAL_NODE_WITHOUT_INDEXING= False
    HAS_LOCAL_NODE_WITH_INDEXING = False
else:
    if HAS_LOCAL_NODE_WITHOUT_INDEXING:
        HAS_LOCAL_NODE_WITH_INDEXING = False

    if HAS_LOCAL_NODE_WITH_INDEXING:
        HAS_LOCAL_NODE_WITHOUT_INDEXING = False

logging.debug(f"HAS_LOCAL_NODE_WITHOUT_INDEXING:{HAS_LOCAL_NODE_WITHOUT_INDEXING}")
logging.debug(f"HAS_LOCAL_NODE_WITH_INDEXING:{HAS_LOCAL_NODE_WITH_INDEXING}")


client = DeSoDexClient(
    is_testnet=False,
    seed_phrase_or_hex=seed_phrase_or_hex,
    passphrase="",
    node_url=BASE_URL if REMOTE_API else "http://localhost:17001"
)


def api_get(endpoint, payload=None,version=0):
    try:
        if REMOTE_API:
            response = requests.post(api_url +"v"+str(version)+"/"+ endpoint, json=payload)
        else:
            if HAS_LOCAL_NODE_WITHOUT_INDEXING:
                if endpoint=="get-notifications":
                    logging.debug("---Using remote node---")
                    response = requests.post(api_url +"v"+str(version)+"/"+ endpoint, json=payload)
                    logging.debug("--------End------------")
                else:
                    response = requests.post(local_url +"v"+str(version)+"/"+ endpoint, json=payload)
            if HAS_LOCAL_NODE_WITH_INDEXING:
                response = requests.post(local_url +"v"+str(version)+"/"+ endpoint, json=payload)
        
            
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"API Error: {e}")
        return None
def node_info():
    payload = {
    }
    data = api_get("node-info", payload,1)
    return data

def get_app_state():
    payload = {
    }
    data = api_get("get-app-state", payload)
    return data
def get_single_profile(Username,PublicKeyBase58Check=""):
    payload = {
        "NoErrorOnMissing": False,
        "PublicKeyBase58Check": PublicKeyBase58Check,
        "Username": Username
    }
    data = api_get("get-single-profile", payload)
    return data


bot_public_key = base58_check_encode(client.deso_keypair.public_key, False)
bot_username = get_single_profile("",bot_public_key)["Profile"]["Username"]
if bot_username is None:
    logging.error("Error,bot username can not get. exit")
    exit()

if info:=get_app_state():
    nodes=info["Nodes"]
    height=info["BlockHeight"]

def get_quote_reposts_for_post(PostHashHex,ReaderPublicKeyBase58Check):
    payload = {
        "Limit":50,
        "Offset":0,
        "PostHashHex": PostHashHex,
        "ReaderPublicKeyBase58Check":ReaderPublicKeyBase58Check
    }
    data = api_get("get-quote-reposts-for-post", payload)
    return data

def get_reposts_for_post(PostHashHex,ReaderPublicKeyBase58Check):
    payload = {
        "Limit":50,
        "Offset":0,
        "PostHashHex": PostHashHex,
        "ReaderPublicKeyBase58Check":ReaderPublicKeyBase58Check
    }
    data = api_get("get-reposts-for-post", payload)
    return data

def get_single_post(post_hash_hex, reader_public_key=None, fetch_parents=False, comment_offset=0, comment_limit=100, add_global_feed=False):
    payload = {
        "PostHashHex": post_hash_hex,
        "FetchParents": fetch_parents,
        "CommentOffset": comment_offset,
        "CommentLimit": comment_limit
    }
    if reader_public_key:
        payload["ReaderPublicKeyBase58Check"] = reader_public_key
    if add_global_feed:
        payload["AddGlobalFeedBool"] = add_global_feed
    data = api_get("get-single-post", payload)
    return data["PostFound"] if "PostFound" in data else None

def get_notifications(PublicKeyBase58Check,FetchStartIndex=-1,NumToFetch=1,FilteredOutNotificationCategories={}):
    payload = {
        "PublicKeyBase58Check": PublicKeyBase58Check,
        "FetchStartIndex": FetchStartIndex,
        "NumToFetch": NumToFetch,
        "FilteredOutNotificationCategories":FilteredOutNotificationCategories
    }
    data = api_get("get-notifications", payload)
    return data


def create_post(body,parent_post_hash_hex):
    logging.info("\n---- Submit Post ----")
    try:
        logging.info('Constructing submit-post txn...')
        post_response = client.submit_post(
            updater_public_key_base58check=bot_public_key,
            body=body,
            parent_post_hash_hex=parent_post_hash_hex,  # Example parent post hash
            title="",
            image_urls=[],
            video_urls=[],
            post_extra_data={"Node": "1","is_bot":"true"},
            min_fee_rate_nanos_per_kb=1000,
            is_hidden=False,
            in_tutorial=False
        )
        logging.info('Signing and submitting txn...')
        submitted_txn_response = client.sign_and_submit_txn(post_response)
        txn_hash = submitted_txn_response['TxnHashHex']
        
        logging.info('SUCCESS!')
        return 1
    except Exception as e:
        logging.error(f"ERROR: Submit post call failed: {e}")
        return 0


def save_to_json(data, filename):
  try:
    with open(filename, 'w') as f:  # 'w' mode: write (overwrites existing file)
      json.dump(data, f, indent=4)  # indent for pretty formatting
    logging.info(f"Data saved to {filename}")
  except TypeError as e:
    logging.error(f"Error: Data is not JSON serializable: {e}")
  except Exception as e:
    logging.error(f"Error saving to file: {e}")

def load_from_json(filename):
  try:
    with open(filename, 'r') as f:  # 'r' mode: read
      data = json.load(f)
    logging.info(f"Data loaded from {filename}")
    return data
  except FileNotFoundError:
    logging.error(f"Error: File not found: {filename}")
    return None  # Important: Return None if file not found
  except json.JSONDecodeError as e:
    logging.error(f"Error decoding JSON in {filename}: {e}")
    return None # Important: Return None if JSON is invalid
  except Exception as e:
    logging.error(f"Error loading from file: {e}")
    return None

def parse_state(paragraph):
    match = re.search(r'@randompicker\s+(\d+)-(\d+)', paragraph)

    if match:
        start = int(match.group(1))
        end = int(match.group(2))
        return [start,end]
    else:
        None
        


def notificationListener():
    profile=get_single_profile("",bot_public_key)
    post_id_list=[]
    lastIndex=-1
    
    if result:=load_from_json("notificationLastIndex_thread.json"):
        lastIndex=result["index"]

    maxIndex=lastIndex

    if result:=load_from_json("postIdList_thread.json"):
        post_id_list=result["post_ids"]

    if result:=load_from_json("parentPostList.json"):
        parent_post_list = result

    while not app_close:
        try:
            currentIndex=-1
            # if result:=load_from_json("notificationLastIndex_thread.json"):
            #     lastIndex=result["index"]
            logging.debug(f"lastIndex:{lastIndex}")

            i=0
            while i<20:#max 20 iteration, total 400 notifications check untill last check index
                i +=1 
                logging.debug(f"currentIndex:{currentIndex}")
                result=get_notifications(profile["Profile"]["PublicKeyBase58Check"],FetchStartIndex=currentIndex,NumToFetch=20,FilteredOutNotificationCategories={"dao coin":True,"user association":True, "post association":True,"post":False,"dao":True,"nft":True,"follow":True,"like":True,"diamond":True,"transfer":True})
                if "Notifications" in result:
                    for notification in result["Notifications"]:
                        #print(f"Notification:{notification}")
                    
                        currentIndex = notification["Index"]
                        logging.debug(f"currentIndex:{currentIndex}")

                        if notification["Index"]>maxIndex: #new mentions
                            logging.info("New mentions")
                            maxIndex = notification["Index"]
                        if currentIndex<lastIndex:
                            logging.debug("Exiting notification loop, currentIndex<lastIndex")
                            break

                                
                        for affectedkeys in notification["Metadata"]["AffectedPublicKeys"]:
                            if affectedkeys["Metadata"]=="MentionedPublicKeyBase58Check":
                                if affectedkeys["PublicKeyBase58Check"]==profile["Profile"]["PublicKeyBase58Check"]:
                                    postId=notification["Metadata"]["SubmitPostTxindexMetadata"]["PostHashBeingModifiedHex"]
                                    if postId in post_id_list:
                                        break
                                    else:
                                        post_id_list.append(postId)
                                        logging.info(postId)
                                        transactor=notification["Metadata"]["TransactorPublicKeyBase58Check"]
                                        if transactor==bot_public_key:
                                            logging.debug("Myself mention skipping")
                                            save_to_json({"post_ids":post_id_list},"postIdList_thread.json")
                                            break
                                        r=get_single_profile("",transactor)
                                        if r is None:
                                            break
                                        username= r["Profile"]["Username"]
                                        mentioned_post = get_single_post(postId,bot_public_key)
                                        body=mentioned_post["Body"]

                                    
                                        logging.debug(f"username: {username}")
                                        logging.debug(f"transactor: {transactor}")
                                        logging.debug(f"body:\n{body}") 
                                        status_res=parse_state(body)
                                        if status_res is None:
                                            start=None
                                            end=None
                                        else:
                                            start,end=status_res

                                        
                                        logging.debug(f"start:{start},stop:{end}")
                                        if start is not None and end is not None:
                                            if end>start:
                                                number = random.randint(start, end)
                                                print(f"Number:{number}")
                                                create_post(f"Your random pick: {number}",postId)
                                            else:
                                                pass
                                                create_post(f"Invalid number range",postId) 
                                        else:
                                            pass
                                            create_post(f"How to use this service: @randompicker 1-10",postId) 


                                        save_to_json({"post_ids":post_id_list},"postIdList_thread.json")

                                        break
                    if currentIndex<20: #end of mentions
                        logging.debug("End of mentions")
                        break 
                    if currentIndex<=lastIndex:
                        logging.debug("Exiting while loop, currentIndex<=lastIndex")
                        break

            if maxIndex > lastIndex:
                logging.debug("maxIndex > lastIndex")
                lastIndex = maxIndex
                save_to_json({"index":lastIndex},"notificationLastIndex_thread.json")

          
                

            for _ in range(NOTIFICATION_UPDATE_INTERVEL):
                time.sleep(1)
                if app_close: 
                    return
        except Exception as e:
            logging.error(e)
            time.sleep(100)


notificationListener()





