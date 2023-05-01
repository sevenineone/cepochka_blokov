import hashlib
import json
import logging
import time
import random
from urllib.parse import urlparse
import threading
import requests
from flask import Flask, jsonify


NODES_PORTS = {
    "node1": 5001,
    "node2": 5002,
    "node3": 5003,
}


class Blockchain:
    def __init__(self, genesis: bool = True):
        self.genesis = genesis
        self.replaced = False
        self.chain = []
        self.nodes = set()
        if self.genesis:
            self.add_block(self.new_block(previous_hash="1", proof=100))

    def register_node(self, address):
        parsed_url = urlparse(address)
        if parsed_url.netloc:
            self.nodes.add(parsed_url.netloc)
        elif parsed_url.path:
            self.nodes.add(parsed_url.path)
        else:
            raise ValueError(f"URL {address} is invalid")

    def valid_chain(self, chain):
        last_block = chain[0]
        current_index = 1
        while current_index < len(chain):
            block = chain[current_index]
            if block["previous_hash"] != self.hash(last_block):
                return False
            if not self.valid_proof(
                last_block["proof"], block["proof"], self.hash(last_block)
            ):
                return False
            last_block = block
            current_index += 1
        return True

    def resolve_conflicts(self):
        new_chain = None
        max_length = len(self.chain)
        for node in self.nodes:
            try:
                response = requests.get(f"http://{node}/chain")
                if response.status_code == 200:
                    length = response.json()["length"]
                    chain = response.json()["chain"]
                    if length > max_length and self.valid_chain(chain):
                        max_length = length
                        new_chain = chain
            except Exception:
                continue
        if new_chain:
            self.chain = new_chain
            self.replaced = True
            return True

        return False

    def new_block(self, proof, previous_hash):
        block = {
            "index": len(self.chain) + 1,
            "timestamp": time.time(),
            "data": "я работаю в криптовалюте",
            "proof": proof,
            "previous_hash": previous_hash,
        }
        return block

    def add_block(self, block):
        self.chain.append(block)

    def is_replaced(self):
        if self.replaced:
            self.replaced = False
            return True
        else:
            return False

    @property
    def last_block(self):
        return self.chain[-1]

    @staticmethod
    def hash(block):
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def proof_of_work(self, last_block):
        last_proof = last_block["proof"]
        last_hash = self.hash(last_block)
        proof = 0
        while self.valid_proof(last_proof, proof, last_hash) is False:
            proof += random.randint(1, 5)
        return proof

    @staticmethod
    def valid_proof(last_proof, proof, last_hash):
        guess = f"{last_proof} {proof} {last_hash}".encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:5] == "00000"


def main(args):
    app = Flask(__name__)
    blockchain = Blockchain(args.genesis)
    logging.basicConfig(level=logging.INFO)
    logging.info(f"[{args.name} node initialized]")
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    time.sleep(1)

    def mine():
        while True:
            last_block = blockchain.last_block
            proof = blockchain.proof_of_work(last_block)
            previous_hash = blockchain.hash(last_block)
            new_block = blockchain.new_block(proof, previous_hash)
            blockchain.resolve_conflicts()
            if not blockchain.is_replaced():
                blockchain.add_block(new_block)
                logging.info(f"[{args.name} node] generated: {new_block}")
            else:
                logging.info(f"[{args.name} node] replaced")

            time.sleep(1)

    @app.route("/chain", methods=["GET"])
    def full_chain():
        response = {
            "chain": blockchain.chain,
            "length": len(blockchain.chain),
        }
        return jsonify(response), 200

    for node, port in NODES_PORTS.items():
        if node != args.name:
            blockchain.register_node(f"http://{node}:{port}/")
    
    server = threading.Thread(target=app.run, args=(args.name, NODES_PORTS[args.name]))
    server.setDaemon(True)
    time.sleep(1)
    blockchain.resolve_conflicts()
    generator = threading.Thread(target=mine)
    server.start()
    generator.start()


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument(
        "--genesis", dest="genesis", default=False, type=bool, help="port to listen on"
    )
    parser.add_argument(
        "--name", dest="name", default="", type=str, help="name of node"
    )
    args = parser.parse_args()
    main(args)
