import hashlib
import json
from uuid import uuid4
from time import time
from flask import Flask
from flask import jsonify
from flask import json


class Blockchain:
    def __init__(self):
        self.current_transactions = []
        self.chain = []
        self.nodes = set()

        # Generate genesis block
        self.new_block(previous_hash = 1, proof = 100)

    def new_block(self, proof, previous_hash = None):
        # create new block in blockchain

        #param 'proof' - proof given by PoW algorithm, or any other algorithm
        #param 'previous_hash' - hash of previous block
        #return - new block
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        } 

        # reset current transaction list
        self.current_transactions = []

        self.chain.append(block)
        return block
        
    def new_transaction(self, sender, recipient, amount):
        # create new transaction to go into next mined Block

        #param 'sender' - address of the sender
        #param 'recipient' - address of the recipient
        #param 'amount' - amount
        #return - the index of the block that will hold this transaction
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })

        return self.last_block['index'] + 1    

    @staticmethod
    def hash(block):
        #creates new sha-256 hash of a block

        #param 'block' - block
        block_string = json.dumps(block, sort_keys = True).encode()
        return hashlib.sha256(block_string).hexdigest() 

    @property
    def last_block(self):
        #returns last block in chain
        return self.chain[-1] 
    
    def proof_of_work(self, last_proof):
        '''
        simple proof of work algorithm:
        - find anumber p' such that hash(pp') contains leading 4 zeroes, where p is the previous p'
        - p is the previous proof, and p' is the new proof

        param 'last_proof' - <int>
        return - <int>
        '''
        
        last_proof = self.last_block['proof']
        last_hash = self.hash(self.last_block)

        proof = 0
        while self.valid_proof(last_proof, proof, last_hash) is False:
            proof += 1

        return proof

    @staticmethod
    def valid_proof(last_proof, proof, last_hash):
        '''
        validates the proof

        param 'last_proof' - <int> previous proof
        param 'proof' - <int> current proof
        return - <bool> True if correct, False if not
        '''
        guess = f'{last_proof}{proof}{last_hash}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

    def valid_chain(self, chain):
        '''
        determine if given blockchain is valid

        param 'chain' - <list> a blockchain
        return - <bool> True if valid, False if not
        '''
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n----------")
            # check that hash of previous block is correct
            if block['previous_hash'] != self.hash(last_block):
                return False
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False
            
            last_block = block
            current_index += 1

        return True


    def resolve_conflicts(self):
        ''' consensus algorithm, resolves conflicts by replacing
            chain with longest one in the network.

            return: <bool> True if chain was replaced, False if not
        '''

        neighbours = self.nodes
        new_chain = None

        # only looking for chains longer than ours
        max_length = len(self.chain)

        # grab and verify chains from all nodes in network
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['Length']
                chain = response.json()['chain']

                # check if length is longer and chain is valid
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # replace our chain if we discovered new, valid chain longer than ours
        if new_chain:
            self.chain = new_chain
            return True

        return False


app = Flask(__name__)

# generate globally unique address for this node
node_identifier = str(uuid4()).replace('-', '')

# instantiate the blockchain
blockchain = Blockchain()

@app.route('/mine', methods = ['GET'])
def mine():
    # run proof of work algorithm to get next proof
    last_block = blockchain.last_block
    proof = blockchain.proof_of_work(last_block)

    # must receive reward for finding proof.
    # sender is "0" to signify that this node has mined new coin.
    blockchain.new_transaction(
        sender = "0",
        recipient = node_identifier,
        amount = 1,
    )

    # forge new block by adding it to chain
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200

@app.route('/transactions/new', methods = ['POST'])
def new_transaction():
    values = request.get_json()

    # check that required fields are POST'ed
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # create new transaction
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201

@app.route('/chain', methods = ['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200



if __name__ == '__main__':
    app.run(host = '0.0.0.0', port = 5000)