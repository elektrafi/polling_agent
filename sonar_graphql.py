from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport

sonar_api_key = """eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIxIiwianRpIjoiZDIwYWJiZWM2NmU2YmY3ZTQwZWVjNjQwNWExYTNmZjA2MmMxMzBhNjJiNTc0MmE5NTJkNDFmZWYwZjhhNTE3NWM5ZjliNzA4NTI3OWI5MjgiLCJpYXQiOjE2NDQ4NjU0NzUsIm5iZiI6MTY0NDg2NTQ3NSwiZXhwIjoyMTQ1OTE2ODAwLCJzdWIiOiI2Iiwic2NvcGVzIjpbXX0.VU9jUPi0-kzjUXH3y78Vb5541xhyfwj8nzKifNjY8pfbQ1fpdcdqG6JRovP__tocORCRFCbxksFVVI5ppBoNq7qSoZXT2YDZ_E3xAPTQnD0i6KhGjat_AbGW34Rx38ILtiN7JBf25rwzW65sy29M0zqnmdxTyPEeImSpFijzCdw4gH4ARL5vCAy91pTYKZU0hlVbrBSqa9faJd8-UPwffqm3d_1l8nTbm91zWWEbXajE89M3vstJReKOJ4x5jGqVGI1oh889A9lBfnoCYjLRct06sVudKFlb93U4MnnBAEZbMI7vIb4XeVPEI6-AisCt06E9K1KlIYmX8kcQH8eXPDYWlPMz9h4dTghzNha19pfWlU8uhlSw8x03N8Ahxg8obGUvKhn3Ee522YCFX-vTGVfdw7GQmE3c02A9SgrWAGoq_rvPhjh8z5Q0eC6NoDB3ERbp_cyktdKw92nuHoupiAhhU766tBXeoaii8KhfUmiQJT7F8K7S2GLb7iQ7QLyU891be4fJilp1jBtD5DUtaT7W2-PTFYBDYx9n0bubxrlgqix_jC7372URfYAgC1Cqchph2BLlhrthZIw4FbYrpvKX1sv_o0PXYg8H_v74TbWA_eplaCHrHSDvBgtnskiARxsEy7x5e9rHotITRezyV39svbn7vSJ2vzCaLz9hZrI"""
sonar_url = 'https://elektrafi.sonar.software/api/graphql'
class SonarGraphQL:
    def __init__(self):
        transport = AIOHTTPTransport(
            url=sonar_url,
            ssl=True,
            ssl_close_timeout=50,
            headers={
                'Authorization': f'Bearer {sonar_api_key}',
                'Accept': 'application/json'
            })
        self.client = Client(transport=transport, fetch_schema_from_transport=True)
        

    def get_users(self):
        query = gql(
            """
            query getAccounts {
                contacts {
                    entities {
                        id,
                        name,
                        primary
                    }
                }
            }
            """
        )
        return self.client.execute(query)

        
if __name__ == '__main__':
    print(SonarGraphQL().get_users())