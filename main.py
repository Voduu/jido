from jisho_api.word import Word

text = ""

while text != 'exit':
    text = input('Enter a word: ')

    r = Word.request(text)
    
    for element in r.data[0].senses[0].english_definitions: 
        print(element)