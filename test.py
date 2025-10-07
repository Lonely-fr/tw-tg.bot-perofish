n=int(input())
a=int(input())
x=int(input())
b=int(input())
y=int(input())
улица = []
for i in range(n):
    улица.append("дом")
if n>a*(1+x*2)+b*(1+y/2):
    print("NO")
else:
    print("YES")
        