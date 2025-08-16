function []=drawHyperplanes(varargin)

opt={};
switch nargin
    case 0
        error 'you need at least one argument'
    case 1
        H=varargin{1};
        [N,d]=size(H);
        if d>3
            error 'space dimension is too large'
        end
        h=ones(N,1);
        a=repmat([-1 1],1,d);
    case 2
        H=varargin{1};
        h=varargin{2};
        [N,d]=size(H);
        if d>3
            error 'space dimension is too large'
        end
        a=repmat([-1 1],1,d);        
    otherwise
        H=varargin{1};
        h=varargin{2};
        a=varargin{3};
        [N,d]=size(H);
            opt={varargin{4:end}};
        if d>3
            error 'space dimension is too large'
        end
end

switch d
    case 2
        axis(a);
        hold on
        grid on
        for i=1:N
            tmp=a(1:2);            
            tmp2=(h(i)-H(i,1)*a(1:2))./H(i,2);
            [~,I]=sort(tmp2);
            tmp=tmp(I);
            tmp2=tmp2(I);
            if tmp2(1)<a(3)
                tmp2(1)=a(3);
                tmp(1)=(h(i)-a(3)*H(i,2))/H(i,1);
            end
            if tmp2(2)>a(4)
                tmp2(2)=a(4);
                tmp(2)=(h(i)-a(4)*H(i,2))/H(i,1);
            end            
            plot(tmp,tmp2,opt{:})
        end
    case 3
        % to do
end